#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


PATTERNS: dict[str, re.Pattern[str]] = {
    "requests_post": re.compile(r"\brequests\.post\b"),
    "requests_request": re.compile(r"\brequests\.request\b"),
    "chat_completions_path": re.compile(r"/chat/completions"),
    "curl": re.compile(r"\bcurl\b"),
    "authorization_bearer": re.compile(r"Authorization\s*:\s*Bearer", re.I),
    "openai_endpoint": re.compile(r"api\.openai\.com|openai\.azure\.com", re.I),
    "openrouter_endpoint": re.compile(r"openrouter\.ai", re.I),
    "anthropic_endpoint": re.compile(r"anthropic\.com|/v1/messages", re.I),
}

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
BINARY_SUFFIXES = {".zip", ".parquet", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".sqlite", ".duckdb"}
MAX_TEXT_SCAN_BYTES = 750_000
SDK_CLIENT_ALLOWED = {
    "dashagent/llm_client.py",
    "scripts/check_llm_sdk_backend.py",
    "scripts/check_openai_compatible_llm.py",
    "scripts/load_local_env.py",
}


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_sdk_usage_audit(config)
    print(
        json.dumps(
            {
                "runtime_llm_direct_http_hits": report["summary"]["runtime_llm_direct_http_hits"],
                "json": str(config.outputs_dir / "reports" / "sdk_usage_audit.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["summary"]["runtime_llm_direct_http_hits"] == 0 else 1


def generate_sdk_usage_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    hits = []
    for path in _iter_text_files(config.project_root):
        rel = path.relative_to(config.project_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_name, pattern in PATTERNS.items():
                if not pattern.search(line):
                    continue
                classification = _classify_hit(rel, line, pattern_name)
                hits.append(
                    {
                        "path": rel,
                        "line": line_number,
                        "pattern": pattern_name,
                        "classification": classification,
                        "is_llm_related": _is_llm_related(rel, line),
                        "action_taken": _action_for(classification),
                        "snippet": _snippet(line),
                    }
                )

    summary = _summary(hits)
    report = {
        "report_type": "sdk_usage_audit",
        "purpose": "System-wide audit that LLM/model calls use dashagent.llm_client.get_llm_client() or LLMClient.",
        "acceptance": {"runtime_llm_direct_http_hits": 0},
        "summary": summary,
        "all_llm_calls_sdk_based": summary["runtime_llm_direct_http_hits"] == 0,
        "required_llm_path": "dashagent.llm_client.get_llm_client() or shared LLMClient abstraction",
        "allowed_provider_sdks": {
            "openai_compatible": "OpenAI SDK",
            "anthropic": "Anthropic SDK",
            "gemini": "Google Gen AI SDK",
        },
        "important_distinction": "Adobe REST/API calls are not LLM/model calls and may continue through the Adobe API client path.",
        "hits": hits,
        "remaining_allowed_exceptions": [
            "SDK client configuration constants for provider base URLs.",
            "Documentation examples that describe SDK-only rules.",
            "Test fixtures that assert direct LLM HTTP is not used.",
            "Generated output/source copies are reported separately and are not runtime code.",
        ],
    }
    safe = redact_secrets(report)
    if not isinstance(safe, dict):
        safe = report
    (reports_dir / "sdk_usage_audit.json").write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / "sdk_usage_audit.md").write_text(_render_markdown(safe), encoding="utf-8")
    return safe


def _iter_text_files(root: Path) -> list[Path]:
    paths = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("outputs/") and not rel.startswith("outputs/reports/"):
            continue
        if rel in {"outputs/reports/sdk_usage_audit.json", "outputs/reports/sdk_usage_audit.md"}:
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_SCAN_BYTES:
                continue
        except OSError:
            continue
        if path.name == ".env.local":
            continue
        try:
            path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def _classify_hit(rel: str, line: str, pattern_name: str) -> str:
    lower_line = line.lower()
    if rel.startswith("outputs/source_code") or rel.startswith("outputs/final_submission") or rel.startswith("outputs/tmp"):
        return "generated_output_stale_copy"
    if rel.startswith("outputs/"):
        return "generated_output_stale_copy"
    if rel in {"README.md", "AGENTS.md"} or rel.endswith(".md"):
        return "documentation_only"
    if rel.startswith("tests/"):
        return "test_fixture_allowed"
    if rel == "scripts/generate_sdk_usage_audit.py":
        return "documentation_only"
    if rel in SDK_CLIENT_ALLOWED:
        return "sdk_client_allowed"
    if "adobe" in lower_line or "platform.adobe" in lower_line or "call_api" in lower_line:
        return "non_llm_adobe_api_allowed"
    if pattern_name in {"openrouter_endpoint", "openai_endpoint", "anthropic_endpoint"} and "base_url" in lower_line:
        return "sdk_client_allowed"
    if _is_llm_related(rel, line):
        return "llm_runtime_refactor_required"
    return "documentation_only"


def _is_llm_related(rel: str, line: str) -> bool:
    text = f"{rel} {line}".lower()
    if any(term in text for term in ["llm", "openai", "openrouter", "anthropic", "chat/completions", "model"]):
        if "adobe" not in text and "call_api" not in text:
            return True
    return False


def _action_for(classification: str) -> str:
    if classification == "llm_runtime_refactor_required":
        return "must_refactor_to_get_llm_client"
    if classification == "sdk_client_allowed":
        return "allowed_sdk_configuration_or_sdk_client_path"
    if classification == "non_llm_adobe_api_allowed":
        return "left_unchanged_non_llm_api_path"
    if classification == "test_fixture_allowed":
        return "allowed_test_fixture_or_guard"
    if classification == "generated_output_stale_copy":
        return "reported_as_generated_output_not_runtime"
    return "documentation_only_no_runtime_action"


def _summary(hits: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(hit["classification"] for hit in hits)
    source_code_hits = sum(
        1
        for hit in hits
        if not hit["path"].startswith("outputs/") and not hit["path"].endswith(".md") and not hit["path"].startswith("tests/")
    )
    generated_output_hits = sum(1 for hit in hits if hit["path"].startswith("outputs/"))
    documentation_hits = sum(1 for hit in hits if hit["classification"] == "documentation_only")
    runtime_hits = sum(1 for hit in hits if hit["classification"] in {"llm_runtime_refactor_required", "sdk_client_allowed", "non_llm_adobe_api_allowed"})
    runtime_llm_direct_http_hits = sum(1 for hit in hits if hit["classification"] == "llm_runtime_refactor_required")
    return {
        "total_hits": len(hits),
        "source_code_hits": source_code_hits,
        "generated_output_hits": generated_output_hits,
        "documentation_hits": documentation_hits,
        "runtime_hits": runtime_hits,
        "runtime_llm_direct_http_hits": runtime_llm_direct_http_hits,
        **{f"classification_{key}": value for key, value in sorted(counts.items())},
    }


def _snippet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"Authorization\s*:\s*Bearer\s+[^\s,;\"']+", "Authorization: [REDACTED]", line, flags=re.I)
    line = re.sub(r"x-api-key\s*=\s*[^\s,;\"']+", "x-api-key=[REDACTED]", line, flags=re.I)
    line = re.sub(r"\b[A-Za-z0-9_.@-]{1,12}\*\*\*", "[REDACTED]", line)
    if len(line) > 180:
        line = line[:177] + "..."
    return line


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# SDK Usage Audit",
        "",
        "This audit checks that LLM/model calls use the shared SDK-based LLM client abstraction.",
        "",
        f"- Runtime LLM direct HTTP hits: `{summary.get('runtime_llm_direct_http_hits')}`",
        f"- Source code hits: `{summary.get('source_code_hits')}`",
        f"- Generated output hits: `{summary.get('generated_output_hits')}`",
        f"- Documentation hits: `{summary.get('documentation_hits')}`",
        f"- Runtime hits: `{summary.get('runtime_hits')}`",
        f"- All LLM calls SDK-based: `{report.get('all_llm_calls_sdk_based')}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in sorted(summary.items()):
        if key.startswith("classification_"):
            lines.append(f"- `{key.removeprefix('classification_')}`: `{value}`")
    lines.extend(["", "## Remaining Allowed Exceptions", ""])
    lines.extend(f"- {item}" for item in report.get("remaining_allowed_exceptions", []))
    lines.extend(["", "The Adobe REST API path is out of scope for the LLM SDK rule and remains unchanged.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
