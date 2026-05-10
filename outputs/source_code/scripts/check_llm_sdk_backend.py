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
from dashagent.llm_client import Anthropic, OpenAI, get_llm_client
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


KEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
AUTH_HEADER_RE = re.compile(r"Authorization\s*:\s*" + r"Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE)


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_llm_sdk_backend_check(config)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "provider": report["provider"],
                "backend_type": report["backend_type"],
                "model": report["model"],
                "tool_calling_supported": report["tool_calling_supported"],
                "json": str(config.outputs_dir / "llm_sdk_backend_check.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_llm_sdk_backend_check(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    load_meta = load_local_env(config.project_root)
    client = get_llm_client()
    provider = client.provider_name()
    if provider == "none":
        configured_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if configured_provider in {"openai", "openai_compatible", "openrouter", "anthropic"}:
            provider = configured_provider
    model = client.model_name()
    backend_type = _backend_type(provider)
    key_visible = _key_visible(provider)
    report: dict[str, Any] = {
        "ok": False,
        "framework": "generic_sdk_llm_baseline",
        "provider": provider,
        "provider_type": _provider_type(provider),
        "backend_type": backend_type,
        "transport": backend_type,
        "sdk_path_used": backend_type in {"openai_sdk", "anthropic_sdk"},
        "base_url": getattr(client, "base_url", None),
        "model": model,
        "backend_name": model,
        "key_visible": key_visible,
        "env_source": _env_source(provider, key_visible, load_meta),
        "sdk_available": _sdk_available(provider),
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
        "notes": ["Generic SDK backend check. Qwen, Claude, GPT, or other models are backend metadata only."],
    }
    if not key_visible or not client.available():
        report["failure_categories"].append(_missing_key_category(provider))
        return _write_report(config, report)
    if not report["sdk_available"]:
        report["failure_categories"].append(f"{provider}_sdk_unavailable")
        return _write_report(config, report)

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


def _run_minimal_chat(client: Any) -> dict[str, Any]:
    response = client.generate_messages(
        [
            {"role": "system", "content": "You are a concise smoke-test assistant."},
            {"role": "user", "content": "Reply with exactly: ok"},
        ]
    )
    return _response_summary(response, attempted=True)


def _run_tool_call_smoke(client: Any) -> dict[str, Any]:
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


def _provider_type(provider: str) -> str:
    if provider == "anthropic":
        return "anthropic"
    if provider in {"openai", "openai_compatible", "openrouter"}:
        return "openai_compatible"
    return "none"


def _backend_type(provider: str) -> str:
    if provider == "anthropic":
        return "anthropic_sdk"
    if provider in {"openai", "openai_compatible", "openrouter"}:
        return "openai_sdk"
    return "none"


def _sdk_available(provider: str) -> bool:
    if provider == "anthropic":
        return Anthropic is not None
    if provider in {"openai", "openai_compatible", "openrouter"}:
        return OpenAI is not None
    return False


def _key_visible(provider: str) -> bool:
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))
    if provider in {"openai", "openai_compatible"}:
        return bool(os.getenv("OPENAI_API_KEY"))
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY"))


def _missing_key_category(provider: str) -> str:
    if provider == "anthropic":
        return "missing_anthropic_api_key"
    return "missing_openai_api_key"


def _env_source(provider: str, key_visible: bool, load_meta: dict[str, Any]) -> str:
    if not key_visible:
        return "none"
    key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    if key_name in set(load_meta.get("keys_loaded") or []):
        return ".env.local"
    return "environment"


def _response_failure_category(response: dict[str, Any], *, default: str = "provider_error") -> str:
    text = json.dumps(response, default=str).lower()
    if "missing" in text and "api_key" in text:
        return "missing_api_key"
    if "rate limit" in text or "429" in text:
        return "rate_limit"
    if "connection" in text or "timeout" in text or "unavailable" in text:
        return "endpoint_unavailable"
    if "tool" in default:
        return default
    return default


def _write_report(config: Config, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    for key in ["base_url", "model", "backend_name", "provider", "provider_type", "backend_type"]:
        safe_report[key] = report.get(key)
    json_path = config.outputs_dir / "llm_sdk_backend_check.json"
    md_path = config.outputs_dir / "llm_sdk_backend_check.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(safe_report), encoding="utf-8")
    return safe_report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LLM SDK Backend Check",
        "",
        f"- Framework: `{report.get('framework')}`",
        f"- Provider: `{report.get('provider')}`",
        f"- Provider type: `{report.get('provider_type')}`",
        f"- Backend type: `{report.get('backend_type')}`",
        f"- SDK path used: `{report.get('sdk_path_used')}`",
        f"- Base URL: `{report.get('base_url') or 'unavailable'}`",
        f"- Current LLM backend: `{report.get('backend_name')}`",
        f"- Key visible: `{report.get('key_visible')}`",
        f"- SDK available: `{report.get('sdk_available')}`",
        f"- Minimal chat ok: `{report.get('minimal_chat', {}).get('ok')}`",
        f"- Tool calling supported: `{report.get('tool_calling_supported')}`",
        f"- Tool finish reason: `{report.get('tool_call_smoke', {}).get('finish_reason')}`",
        f"- First tool name: `{report.get('tool_call_smoke', {}).get('first_tool_name')}`",
        f"- Failure categories: `{', '.join(report.get('failure_categories') or []) or 'none'}`",
        "",
        "The LLM baseline framework is generic; the configured provider/model is backend metadata.",
    ]
    return "\n".join(lines) + "\n"


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
