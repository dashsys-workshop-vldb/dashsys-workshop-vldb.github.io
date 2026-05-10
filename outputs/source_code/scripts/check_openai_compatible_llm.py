#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL, OpenAI, OpenAILLMClient
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


KEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
AUTH_HEADER_RE = re.compile(r"Authorization\s*:\s*" + r"Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE)


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_openai_compatible_llm_check(config)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "key_visible": report["key_visible"],
                "model": report["model"],
                "tool_calling_supported": report["tool_calling_supported"],
                "json": str(config.outputs_dir / "openai_compatible_llm_check.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_openai_compatible_llm_check(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    load_meta = load_local_env(config.project_root)
    base_url = os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    key_visible = bool(os.getenv("OPENAI_API_KEY"))
    report: dict[str, Any] = {
        "ok": False,
        "provider": "openai_compatible",
        "key_visible": key_visible,
        "base_url": base_url,
        "model": model,
        "env_source": ".env.local" if "OPENAI_API_KEY" in set(load_meta.get("keys_loaded") or []) else ("environment" if key_visible else "none"),
        "sdk_available": OpenAI is not None,
        "model_listing": {"attempted": False, "ok": False, "model_available": "unknown", "error": ""},
        "minimal_chat": {"attempted": False, "ok": False, "finish_reason": None, "transport": None, "error": ""},
        "tool_call_smoke": {
            "attempted": False,
            "ok": False,
            "finish_reason": None,
            "first_tool_name": None,
            "tool_call_count": 0,
            "transport": None,
            "error": "",
        },
        "tool_calling_supported": False,
        "failure_categories": [],
    }
    if not key_visible:
        report["failure_categories"].append("missing_openai_api_key")
        return _write_report(config, report)
    if OpenAI is None:
        report["failure_categories"].append("openai_sdk_unavailable")

    report["model_listing"] = _check_model_listing(base_url=base_url, model=model)

    client = OpenAILLMClient(model=model, base_url=base_url, timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")))
    report["minimal_chat"] = _run_minimal_chat(client)
    if not report["minimal_chat"].get("ok"):
        report["failure_categories"].append(_response_failure_category(report["minimal_chat"]))

    report["tool_call_smoke"] = _run_tool_call_smoke(client)
    report["tool_calling_supported"] = bool(
        report["tool_call_smoke"].get("finish_reason") == "tool_calls"
        and report["tool_call_smoke"].get("first_tool_name") == "execute_sql"
    )
    report["tool_call_smoke"]["ok"] = report["tool_calling_supported"]
    if not report["tool_calling_supported"]:
        report["failure_categories"].append(_response_failure_category(report["tool_call_smoke"], default="tool_calling_not_supported"))

    report["ok"] = bool(report["minimal_chat"].get("ok") and report["tool_calling_supported"])
    return _write_report(config, report)


def _check_model_listing(*, base_url: str, model: str) -> dict[str, Any]:
    result: dict[str, Any] = {"attempted": True, "ok": False, "model_available": "unknown", "model_count": 0, "error": ""}
    if OpenAI is None:
        result["error"] = "OpenAI SDK is not installed."
        return result
    try:
        sdk = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url, timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")))
        listing = sdk.models.list()
        if hasattr(listing, "model_dump"):
            body = listing.model_dump()
        elif hasattr(listing, "dict"):
            body = listing.dict()
        else:
            body = json.loads(json.dumps(listing, default=lambda obj: getattr(obj, "__dict__", str(obj))))
        ids = [item.get("id") for item in body.get("data", []) if isinstance(item, dict)]
        result.update({"ok": True, "model_available": model in ids, "model_count": len(ids)})
    except Exception as exc:
        result["error"] = _redact_text(str(exc))[:500]
    return result


def _run_minimal_chat(client: OpenAILLMClient) -> dict[str, Any]:
    response = client.generate_messages(
        [
            {"role": "system", "content": "You are a concise smoke-test assistant."},
            {"role": "user", "content": "Reply with exactly: ok"},
        ]
    )
    return _response_summary(response, attempted=True)


def _run_tool_call_smoke(client: OpenAILLMClient) -> dict[str, Any]:
    response = client.generate_messages(
        [
            {
                "role": "user",
                "content": (
                    "Use the execute_sql tool to inspect the local database. "
                    "Call execute_sql with SQL: SELECT COUNT(*) AS count FROM dim_blueprint"
                ),
            }
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "execute_sql",
                    "description": "Execute a read-only SQL query.",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        tool_choice="auto",
    )
    summary = _response_summary(response, attempted=True)
    tool_calls = response.get("tool_calls") or []
    summary["tool_call_count"] = len(tool_calls)
    summary["first_tool_name"] = tool_calls[0].get("name") if tool_calls else None
    return summary


def _response_summary(response: dict[str, Any], *, attempted: bool) -> dict[str, Any]:
    return {
        "attempted": attempted,
        "ok": bool(response.get("ok")),
        "finish_reason": response.get("finish_reason"),
        "transport": response.get("transport"),
        "content_preview": _redact_text(str(response.get("content") or ""))[:120],
        "tool_call_count": len(response.get("tool_calls") or []),
        "first_tool_name": (response.get("tool_calls") or [{}])[0].get("name") if response.get("tool_calls") else None,
        "error": _redact_text(str(response.get("error") or response.get("reason") or ""))[:500],
    }


def _response_failure_category(response: dict[str, Any], *, default: str = "provider_error") -> str:
    text = json.dumps(response, default=str).lower()
    if "missing_openai_api_key" in text or "api key is not set" in text:
        return "missing_openai_api_key"
    if "rate limit" in text or "429" in text:
        return "rate_limit"
    if "connection" in text or "timeout" in text or "unavailable" in text:
        return "endpoint_unavailable"
    if "tool" in default:
        return default
    return default


def _write_report(config: Config, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    safe_report["base_url"] = report.get("base_url")
    safe_report["model"] = report.get("model")
    safe_report["provider"] = report.get("provider")
    json_path = config.outputs_dir / "openai_compatible_llm_check.json"
    md_path = config.outputs_dir / "openai_compatible_llm_check.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# OpenAI-Compatible LLM Check",
        "",
        f"- Provider: `{safe_report.get('provider')}`",
        f"- Base URL: `{safe_report.get('base_url')}`",
        f"- Model: `{safe_report.get('model')}`",
        f"- Key visible: `{safe_report.get('key_visible')}`",
        f"- SDK available: `{safe_report.get('sdk_available')}`",
        f"- Minimal chat ok: `{safe_report.get('minimal_chat', {}).get('ok')}`",
        f"- Tool calling supported: `{safe_report.get('tool_calling_supported')}`",
        f"- Tool finish reason: `{safe_report.get('tool_call_smoke', {}).get('finish_reason')}`",
        f"- First tool name: `{safe_report.get('tool_call_smoke', {}).get('first_tool_name')}`",
        f"- Failure categories: `{', '.join(safe_report.get('failure_categories') or []) or 'none'}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return safe_report


def _redact_text(text: str) -> str:
    redacted = redact_secrets(text)
    if not isinstance(redacted, str):
        redacted = str(redacted)
    redacted = AUTH_HEADER_RE.sub("Authorization: " + "Bearer [REDACTED]", redacted)
    redacted = BEARER_RE.sub("Bearer [REDACTED]", redacted)
    redacted = KEY_LIKE_RE.sub("[REDACTED]", redacted)
    return redacted


if __name__ == "__main__":
    raise SystemExit(main())
