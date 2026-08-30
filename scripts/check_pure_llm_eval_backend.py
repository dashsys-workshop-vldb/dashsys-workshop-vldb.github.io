#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import AnthropicLLMClient, OpenAILLMClient, OpenRouterLLMClient
from scripts.load_local_env import load_local_env

REPORT_STEM = "pure_llm_eval_backend_check"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_backend_check(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "providers": report["providers"]}, indent=2, sort_keys=True))
    return 0


def run_backend_check(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    old_max = os.environ.get("LLM_MAX_TOKENS")
    os.environ["LLM_MAX_TOKENS"] = "32"
    providers = [_probe(provider, client, env_names) for provider, client, env_names in _provider_specs()]
    if old_max is None:
        os.environ.pop("LLM_MAX_TOKENS", None)
    else:
        os.environ["LLM_MAX_TOKENS"] = old_max
    # Provider rows are constructed from a small allowlist of non-secret fields.
    # Keep model names visible because backend readiness reporting needs them.
    report = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_allowed": False,
        "packaged_runtime_changed": False,
        "providers": providers,
        "at_least_one_hosted_row_allowed": any(row["auth_status"] == "ok" for row in providers),
    }
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _provider_specs() -> list[tuple[str, Any, list[str]]]:
    selected = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    specs: list[tuple[str, Any, list[str]]] = []
    if selected in {"openai", "openai_compatible"} or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_MODEL"):
        specs.append(("openai", OpenAILLMClient(timeout_seconds=20), ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "LLM_PROVIDER", "LLM_MAX_TOKENS"]))
    if selected == "openrouter" or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_BASE_URL") or os.getenv("OPENROUTER_MODEL"):
        specs.append(("openrouter", OpenRouterLLMClient(timeout_seconds=20), ["OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "OPENROUTER_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_PROVIDER", "LLM_MAX_TOKENS"]))
    if selected == "anthropic" or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_BASE_URL") or os.getenv("ANTHROPIC_MODEL"):
        specs.append(("anthropic", AnthropicLLMClient(timeout_seconds=20), ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "LLM_PROVIDER", "LLM_MAX_TOKENS"]))
    return specs or [("openai", OpenAILLMClient(timeout_seconds=20), ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "LLM_PROVIDER", "LLM_MAX_TOKENS"])]


def _probe(provider: str, client: Any, env_names: list[str]) -> dict[str, Any]:
    key_present = bool(getattr(client, "api_key", None))
    row = {
        "provider": provider,
        "backend_type": "anthropic_sdk" if provider == "anthropic" else "openai_sdk",
        "model_name": client.model_name(),
        "base_url_host_only": _host_only(getattr(client, "base_url", None)),
        "api_key_present": key_present,
        "auth_status": "401" if not key_present else "timeout",
        "tool_calling_supported": False,
        "env_variable_names_to_check_if_401": env_names,
    }
    if not key_present:
        return row
    start = time.monotonic()
    response = client.generate_messages([{"role": "user", "content": "Reply exactly ok."}])
    row["auth_status"] = _classify(response, time.monotonic() - start)
    if row["auth_status"] != "ok":
        return row
    tool_response = client.generate_messages(
        [{"role": "user", "content": "Call execute_sql with SQL: SELECT 1 AS ok"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "execute_sql",
                    "description": "Execute read-only SQL.",
                    "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"], "additionalProperties": False},
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "execute_sql"}},
        parallel_tool_calls=False,
    )
    row["tool_calling_supported"] = bool(tool_response.get("ok") and (tool_response.get("finish_reason") == "tool_calls" or tool_response.get("tool_calls")))
    return row


def _classify(response: dict[str, Any], elapsed: float) -> str:
    text = json.dumps(response, default=str).lower()
    if response.get("ok"):
        return "ok"
    if "401" in text or "unauthorized" in text or "invalid api key" in text or "user not found" in text:
        return "401"
    if "403" in text or "forbidden" in text or "permission" in text:
        return "403"
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate_limited"
    if "model_not_found" in text or "model not found" in text or ("404" in text and "model" in text):
        return "model_not_found"
    if "timeout" in text or "timed out" in text or elapsed >= 18:
        return "timeout"
    return "403"


def _host_only(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    return parsed.netloc or str(url).split("/")[0]


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Pure LLM Eval Backend Check",
        "",
        "| provider | backend type | model name | base_url host | api_key_present | auth status | tool_calling_supported |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["providers"]:
        lines.append(
            f"| `{row['provider']}` | `{row['backend_type']}` | `{row['model_name']}` | `{row['base_url_host_only']}` | `{row['api_key_present']}` | `{row['auth_status']}` | `{row['tool_calling_supported']}` |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
