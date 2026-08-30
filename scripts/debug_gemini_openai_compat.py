#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import OpenAILLMClient
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


REPORT_DIR = ROOT / "outputs" / "reports" / "gemini_toolcall_probe"
REPORT_STEM = "gemini_openai_compat_debug"

BASE_URLS = [
    "https://generativelanguage.googleapis.com/v1beta/openai",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
]

MODEL_IDS = [
    "gemini-flash-latest",
    "models/gemini-flash-latest",
    "gemini-2.0-flash",
    "models/gemini-2.0-flash",
]

PROBE_TOOL_NAME = "submit_probe_result"

_GEMINI_KEY_RE = re.compile(r"AIza[A-Za-z0-9_-]{20,}")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(r"Authorization\s*:\s*Bearer\s+[^\s,'\"}]+", re.IGNORECASE)


@dataclass(frozen=True)
class PayloadCase:
    payload_type: str
    payload_label: str
    messages: list[dict[str, str]]
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None


CompletionRunner = Callable[[str, str, PayloadCase, str], Any]


def probe_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": PROBE_TOOL_NAME,
            "description": "Submit classification",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
                    "reason": {"type": "string"},
                },
                "required": ["route", "reason"],
                "additionalProperties": False,
            },
        },
    }


def payload_cases() -> list[PayloadCase]:
    tool = probe_tool_schema()
    return [
        PayloadCase(
            payload_type="basic_no_tools",
            payload_label="A",
            messages=[{"role": "user", "content": "Say hello"}],
        ),
        PayloadCase(
            payload_type="simple_json_no_tools",
            payload_label="B",
            messages=[{"role": "user", "content": 'Return JSON: {"ok": true}'}],
        ),
        PayloadCase(
            payload_type="tool_auto",
            payload_label="C",
            messages=[{"role": "user", "content": "Classify this prompt as DIRECT or EVIDENCE: What is a schema?"}],
            tools=[tool],
            tool_choice="auto",
        ),
        PayloadCase(
            payload_type="tool_forced",
            payload_label="D",
            messages=[{"role": "user", "content": "Classify this prompt as DIRECT or EVIDENCE: What is a schema?"}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": PROBE_TOOL_NAME}},
        ),
    ]


def run_gemini_openai_compat_debug(
    config: Config | None = None,
    *,
    report_dir: Path | None = None,
    completion_runner: CompletionRunner | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_meta = load_local_env(config.project_root)
    api_key = os.getenv("GEMINI_API_KEY") or ""
    key_present = bool(api_key)

    rows: list[dict[str, Any]] = []
    setup_error = None
    sdk_available = _openai_sdk_available()
    if not key_present:
        setup_error = "GEMINI_API_KEY is not set"
    elif completion_runner is None and not sdk_available:
        setup_error = "OpenAI SDK is not installed"

    if setup_error:
        for base_url in BASE_URLS:
            for model in MODEL_IDS:
                for case in payload_cases():
                    rows.append(
                        _error_row(
                            base_url=base_url,
                            model=model,
                            case=case,
                            error=setup_error,
                            status_code=None,
                            elapsed_ms=0.0,
                        )
                    )
    else:
        runner = completion_runner or _openai_sdk_completion
        for base_url in BASE_URLS:
            for model in MODEL_IDS:
                for case in payload_cases():
                    rows.append(_run_one_cell(runner, api_key, base_url, model, case))

    classification = classify_matrix(rows)
    report = {
        "report_type": REPORT_STEM,
        "purpose": "Minimal Gemini OpenAI-compatible chat-completions compatibility matrix for no-tools and tool-choice payloads.",
        "docs_source": {
            "context7_library_id": "/websites/ai_google_dev_gemini-api",
            "compat_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/" + "chat" + "/" + "completions",
            "note": "Context7 Gemini API OpenAI compatibility docs show OpenAI SDK base_url ending in /v1beta/openai/ and tool_choice auto.",
        },
        "gemini_api_key_present": key_present,
        "env_source": ".env.local" if "GEMINI_API_KEY" in set(load_meta.get("keys_loaded") or []) else ("environment" if key_present else "none"),
        "openai_sdk_available": sdk_available,
        "base_urls_tested": BASE_URLS,
        "models_tested": MODEL_IDS,
        "payload_types_tested": [case.payload_type for case in payload_cases()],
        "classification": classification,
        "basic_no_tools_any_ok": any(row["ok"] for row in rows if row["payload_type"] == "basic_no_tools"),
        "tool_payload_any_ok": any(row["ok"] for row in rows if row["payload_type"] in {"tool_auto", "tool_forced"}),
        "tool_call_any_returned": any(int(row.get("tool_calls_count") or 0) > 0 for row in rows if row["payload_type"] in {"tool_auto", "tool_forced"}),
        "v2_smoke_should_run": False,
        "v2_smoke_note": "Per task instruction, this script does not run V2 smoke. Run it only after a tool payload succeeds.",
        "summary": summarize_rows(rows),
        "rows": rows,
    }
    return _write_report(report_dir, report)


def _run_one_cell(runner: CompletionRunner, api_key: str, base_url: str, model: str, case: PayloadCase) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = runner(api_key, base_url, case, model)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        status_code = _status_code_from_exception(exc)
        return _error_row(
            base_url=base_url,
            model=model,
            case=case,
            error=str(exc),
            status_code=status_code,
            elapsed_ms=elapsed_ms,
        )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    body = _response_to_dict(response)
    choice = _first_choice(body)
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
    content = message.get("content")
    return {
        "base_url": base_url,
        "model": model,
        "payload_type": case.payload_type,
        "payload_label": case.payload_label,
        "ok": True,
        "status_code": 200,
        "error_category": "ok",
        "finish_reason": choice.get("finish_reason"),
        "content_present": bool(content),
        "tool_calls_count": len(tool_calls),
        "error_message_redacted": "",
        "bad_request_400": False,
        "elapsed_ms": elapsed_ms,
    }


def _openai_sdk_completion(api_key: str, base_url: str, case: PayloadCase, model: str) -> Any:
    client = OpenAILLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=int(os.getenv("GEMINI_OPENAI_COMPAT_TIMEOUT_SEC", "30")),
    )
    if not client.sdk_available():  # pragma: no cover - guarded by setup check.
        raise RuntimeError("OpenAI SDK is not installed")
    payload: dict[str, Any] = {
        "model": model,
        "messages": case.messages,
    }
    if case.tools:
        payload["tools"] = case.tools
    if case.tool_choice is not None:
        payload["tool_choice"] = case.tool_choice
    return client._create_with_sdk(payload)


def _openai_sdk_available() -> bool:
    return OpenAILLMClient(api_key="probe", base_url=BASE_URLS[0], model=MODEL_IDS[0]).sdk_available()


def _error_row(
    *,
    base_url: str,
    model: str,
    case: PayloadCase,
    error: str,
    status_code: int | None,
    elapsed_ms: float,
) -> dict[str, Any]:
    category = classify_error(status_code, error)
    return {
        "base_url": base_url,
        "model": model,
        "payload_type": case.payload_type,
        "payload_label": case.payload_label,
        "ok": False,
        "status_code": status_code,
        "error_category": category,
        "finish_reason": None,
        "content_present": False,
        "tool_calls_count": 0,
        "error_message_redacted": _redact_text(error)[:700],
        "bad_request_400": category == "bad_request_400",
        "elapsed_ms": elapsed_ms,
    }


def classify_matrix(rows: list[dict[str, Any]]) -> str:
    basic_rows = [row for row in rows if row.get("payload_type") == "basic_no_tools"]
    tool_rows = [row for row in rows if row.get("payload_type") in {"tool_auto", "tool_forced"}]
    auto_rows = [row for row in rows if row.get("payload_type") == "tool_auto"]
    forced_rows = [row for row in rows if row.get("payload_type") == "tool_forced"]
    if basic_rows and not any(row.get("ok") for row in basic_rows):
        return "endpoint_or_base_url_contract_problem"
    if tool_rows and not any(row.get("ok") for row in tool_rows):
        return "tools_schema_or_tool_choice_problem"
    if any(row.get("ok") for row in auto_rows) and forced_rows and not any(row.get("ok") for row in forced_rows):
        return "forced_tool_choice_not_supported"
    if any(row.get("ok") for row in tool_rows):
        return "toolcall_supported"
    return "inconclusive"


def classify_error(status_code: int | None, text: str) -> str:
    lower = str(text or "").lower()
    if status_code == 400 or "400" in lower or "bad request" in lower or "invalid_argument" in lower:
        return "bad_request_400"
    if status_code in {401, 403} or any(marker in lower for marker in ("unauthorized", "forbidden", "authentication", "invalid api key")):
        return "auth_or_permission"
    if status_code == 404 or any(marker in lower for marker in ("404", "not found", "model_not_found", "does not exist")):
        return "not_found_or_model"
    if status_code == 429 or "rate limit" in lower or "quota" in lower:
        return "rate_or_quota"
    if any(marker in lower for marker in ("timeout", "timed out")):
        return "timeout"
    if any(marker in lower for marker in ("connection", "network", "dns", "enotfound")):
        return "network"
    if "openai sdk is not installed" in lower:
        return "openai_sdk_missing"
    if "gemini_api_key is not set" in lower:
        return "missing_api_key"
    return "provider_or_sdk_error"


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_payload: dict[str, dict[str, int]] = {}
    by_base_url: dict[str, dict[str, int]] = {}
    by_model: dict[str, dict[str, int]] = {}
    error_categories: dict[str, int] = {}
    for row in rows:
        _bump_summary(by_payload, str(row["payload_type"]), bool(row["ok"]))
        _bump_summary(by_base_url, str(row["base_url"]), bool(row["ok"]))
        _bump_summary(by_model, str(row["model"]), bool(row["ok"]))
        category = str(row.get("error_category") or "unknown")
        error_categories[category] = error_categories.get(category, 0) + 1
    return {
        "total_cells": len(rows),
        "ok_cells": sum(1 for row in rows if row.get("ok")),
        "bad_request_400_cells": sum(1 for row in rows if row.get("bad_request_400")),
        "by_payload_type": by_payload,
        "by_base_url": by_base_url,
        "by_model": by_model,
        "error_categories": dict(sorted(error_categories.items())),
    }


def _bump_summary(target: dict[str, dict[str, int]], key: str, ok: bool) -> None:
    bucket = target.setdefault(key, {"total": 0, "ok": 0, "failed": 0})
    bucket["total"] += 1
    if ok:
        bucket["ok"] += 1
    else:
        bucket["failed"] += 1


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        dumped = response.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(response, "dict"):
        dumped = response.dict()
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(response, dict):
        return response
    try:
        return json.loads(json.dumps(response, default=lambda obj: getattr(obj, "__dict__", str(obj))))
    except Exception:
        return {}


def _first_choice(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices") if isinstance(body.get("choices"), list) else []
    first = choices[0] if choices else {}
    return first if isinstance(first, dict) else {}


def _status_code_from_exception(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    match = re.search(r"\b([1-5]\d\d)\b", str(exc))
    return int(match.group(1)) if match else None


def _redact_text(text: str) -> str:
    redacted = redact_secrets(str(text or ""))
    if not isinstance(redacted, str):
        redacted = str(redacted)
    redacted = _AUTH_HEADER_RE.sub("Authorization: " + "Bearer [REDACTED]", redacted)
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
    redacted = _GEMINI_KEY_RE.sub("[REDACTED]", redacted)
    return redacted.replace(os.getenv("GEMINI_API_KEY") or "\0", "[REDACTED]")


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    if not isinstance(safe_report, dict):
        safe_report = report
    json_path = report_dir / f"{REPORT_STEM}.json"
    md_path = report_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_render_markdown(safe_report), encoding="utf-8")
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    return safe_report


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Gemini OpenAI-Compatible Compatibility Debug",
        "",
        "Minimal chat-completions matrix only. This report does not run V2 smoke, Pioneer, or benchmarks.",
        "",
        f"- Classification: `{report.get('classification')}`",
        f"- GEMINI_API_KEY present: `{report.get('gemini_api_key_present')}`",
        f"- Env source: `{report.get('env_source')}`",
        f"- OpenAI SDK available: `{report.get('openai_sdk_available')}`",
        f"- Basic no-tools any ok: `{report.get('basic_no_tools_any_ok')}`",
        f"- Tool payload any ok: `{report.get('tool_payload_any_ok')}`",
        f"- Tool call any returned: `{report.get('tool_call_any_returned')}`",
        f"- Bad-request 400 cells: `{summary.get('bad_request_400_cells')}` / `{summary.get('total_cells')}`",
        f"- V2 smoke should run now: `{report.get('v2_smoke_should_run')}`",
        "",
        "## Matrix",
        "",
        "| Base URL | Model | Payload | OK | Category | 400? | Finish | Content? | Tool Calls | Error |",
        "|---|---|---|---:|---|---:|---|---:|---:|---|",
    ]
    for row in report.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md(row.get('base_url'))}`",
                    f"`{_md(row.get('model'))}`",
                    f"`{_md(row.get('payload_type'))}`",
                    f"`{row.get('ok')}`",
                    f"`{_md(row.get('error_category'))}`",
                    f"`{row.get('bad_request_400')}`",
                    f"`{_md(row.get('finish_reason'))}`",
                    f"`{row.get('content_present')}`",
                    f"`{row.get('tool_calls_count')}`",
                    _md(row.get("error_message_redacted") or ""),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Rules",
            "",
            "- If basic no-tools fails for all cells, classification is `endpoint_or_base_url_contract_problem`.",
            "- If basic no-tools succeeds but all tool payloads fail, classification is `tools_schema_or_tool_choice_problem`.",
            "- If `tool_auto` succeeds but all forced tool-choice cells fail, classification is `forced_tool_choice_not_supported`.",
            "- If any tool payload succeeds, classification is `toolcall_supported` unless the forced-only distinction above applies.",
            "",
        ]
    )
    return "\n".join(lines)


def _md(value: Any) -> str:
    text = str(value if value is not None else "")
    text = _redact_text(text)
    text = text.replace("|", "\\|").replace("\n", " ")
    return text[:300]


def main() -> int:
    report = run_gemini_openai_compat_debug()
    print(
        json.dumps(
            {
                "classification": report.get("classification"),
                "gemini_api_key_present": report.get("gemini_api_key_present"),
                "basic_no_tools_any_ok": report.get("basic_no_tools_any_ok"),
                "tool_payload_any_ok": report.get("tool_payload_any_ok"),
                "tool_call_any_returned": report.get("tool_call_any_returned"),
                "bad_request_400_cells": (report.get("summary") or {}).get("bad_request_400_cells"),
                "total_cells": (report.get("summary") or {}).get("total_cells"),
                "json": report.get("json_path"),
                "md": report.get("md_path"),
                "v2_smoke_should_run": report.get("v2_smoke_should_run"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
