#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL, get_llm_client, is_gemini_openai_compat_base_url
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


REPORT_DIR = ROOT / "outputs" / "reports" / "hermes_toolcall_probe"
PROBE_TOOL_NAME = "submit_probe_result"
GEMINI_OPENAI_COMPAT_HOST = "generativelanguage.googleapis.com"


def probe_tool_schema(openai_compat_provider: str | None = None) -> dict[str, Any]:
    if openai_compat_provider == "gemini":
        parameters = {
            "type": "object",
            "properties": {
                "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
                "reason": {"type": "string"},
            },
            "required": ["route", "reason"],
        }
        description = "Submit classification"
    else:
        parameters = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
                "reason": {"type": "string"},
            },
            "required": ["route", "reason"],
        }
        description = "Submit a minimal route classification for the Hermes SDK toolcall probe."
    return {
        "type": "function",
        "function": {
            "name": PROBE_TOOL_NAME,
            "description": description,
            "parameters": parameters,
        },
    }


def run_hermes_toolcall_probe(config: Config | None = None, *, client: Any | None = None, report_dir: Path | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_meta = load_local_env(config.project_root)
    provider_env = (os.getenv("DASHAGENT_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "").strip().lower()
    model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    base_url = os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    openai_compat_provider = _openai_compat_provider(base_url)
    key_present = bool(os.getenv("OPENAI_API_KEY"))
    report: dict[str, Any] = {
        "ok": False,
        "provider_expected": "openai",
        "provider_env": provider_env or "auto",
        "provider": None,
        "openai_compat_provider": openai_compat_provider,
        "model": model,
        "endpoint_label": os.getenv("LLM_ENDPOINT_LABEL") or "",
        "openai_base_url_present": bool(os.getenv("OPENAI_BASE_URL")),
        "openai_base_url_redacted": _redacted_host(base_url),
        "openai_api_key_present": key_present,
        "env_source": ".env.local" if "OPENAI_API_KEY" in set(load_meta.get("keys_loaded") or []) else ("environment" if key_present else "none"),
        "sdk_path_used": False,
        "toolcall_supported": False,
        "tool_calls_count": 0,
        "tool_name": None,
        "finish_reason": None,
        "tool_call_warning": None,
        "gemini_openai_compat_mode": openai_compat_provider == "gemini",
        "payload_keys": [],
        "omitted_for_gemini": [],
        "error": "",
        "response_summary": {},
        "pioneer_used": False,
    }
    if provider_env == "pioneer_chat":
        report["error"] = "DASHAGENT_LLM_PROVIDER selects pioneer_chat; Hermes probe requires OpenAI-compatible SDK provider."
        return _write_probe_report(report_dir, report)
    if client is None:
        client = get_llm_client("openai")
    provider_name = str(client.provider_name())
    report["provider"] = provider_name
    report["pioneer_used"] = provider_name == "pioneer_chat"
    if report["pioneer_used"]:
        report["error"] = "Pioneer provider is not allowed for Hermes SDK toolcall probe."
        return _write_probe_report(report_dir, report)
    response = client.generate_messages(
        _probe_messages(openai_compat_provider),
        tools=[probe_tool_schema(openai_compat_provider)],
        tool_choice=_probe_tool_choice(openai_compat_provider),
        parallel_tool_calls=_probe_parallel_tool_calls(openai_compat_provider),
    )
    tool_calls = response.get("tool_calls") or []
    first_tool = tool_calls[0] if tool_calls else {}
    report.update(
        {
            "provider": response.get("provider") or provider_name,
            "model": response.get("model") or model,
            "sdk_path_used": bool(response.get("sdk_path_used")),
            "tool_calls_count": len(tool_calls),
            "tool_name": first_tool.get("name") or first_tool.get("tool"),
            "finish_reason": response.get("finish_reason"),
            "tool_call_warning": response.get("tool_call_warning"),
            "gemini_openai_compat_mode": bool(response.get("gemini_openai_compat_mode")),
            "payload_keys": response.get("payload_keys") or [],
            "omitted_for_gemini": response.get("omitted_for_gemini") or [],
            "error": _redact_text(str(response.get("error") or response.get("reason") or ""))[:500],
            "response_summary": {
                "ok": bool(response.get("ok")),
                "transport": response.get("transport"),
                "backend_type": response.get("backend_type"),
                "content_present": bool(response.get("content")),
                "tool_call_warning": response.get("tool_call_warning"),
                "payload_keys": response.get("payload_keys") or [],
                "omitted_for_gemini": response.get("omitted_for_gemini") or [],
            },
        }
    )
    report["toolcall_supported"] = bool(response.get("ok") and report["sdk_path_used"] and report["tool_calls_count"] > 0 and report["tool_name"] == PROBE_TOOL_NAME)
    report["ok"] = report["toolcall_supported"]
    if not report["toolcall_supported"] and not report["error"]:
        report["error"] = "Model returned content or empty response without native SDK tool_calls."
    return _write_probe_report(report_dir, report)


def _openai_compat_provider(base_url: str) -> str:
    return "gemini" if is_gemini_openai_compat_base_url(base_url) else ""


def _probe_messages(openai_compat_provider: str) -> list[dict[str, str]]:
    if openai_compat_provider == "gemini":
        return [{"role": "user", "content": "Classify: What is a schema? You must call the tool."}]
    return [
        {"role": "system", "content": "Use the submit_probe_result tool. Do not answer in text."},
        {"role": "user", "content": "Classify this prompt: What is a schema?"},
    ]


def _probe_tool_choice(openai_compat_provider: str) -> str | dict[str, Any]:
    if openai_compat_provider == "gemini":
        return "auto"
    return {"type": "function", "function": {"name": PROBE_TOOL_NAME}}


def _probe_parallel_tool_calls(openai_compat_provider: str) -> bool | None:
    if openai_compat_provider == "gemini":
        return None
    return False


def _write_probe_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    if isinstance(safe_report, dict) and report.get("model"):
        safe_report["model"] = report.get("model")
    json_path = report_dir / "hermes_toolcall_probe.json"
    md_path = report_dir / "hermes_toolcall_probe.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_probe_markdown(safe_report), encoding="utf-8")
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    return safe_report


def _probe_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes SDK Toolcall Probe",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- provider: `{report.get('provider')}`",
        f"- openai_compat_provider: `{report.get('openai_compat_provider')}`",
        f"- model: `{report.get('model')}`",
        f"- OPENAI_BASE_URL present: `{report.get('openai_base_url_present')}`",
        f"- OPENAI_BASE_URL host: `{report.get('openai_base_url_redacted')}`",
        f"- OPENAI_API_KEY present: `{report.get('openai_api_key_present')}`",
        f"- sdk_path_used: `{report.get('sdk_path_used')}`",
        f"- toolcall_supported: `{report.get('toolcall_supported')}`",
        f"- tool_calls_count: `{report.get('tool_calls_count')}`",
        f"- tool_name: `{report.get('tool_name')}`",
        f"- finish_reason: `{report.get('finish_reason')}`",
        f"- tool_call_warning: `{report.get('tool_call_warning')}`",
        f"- gemini_openai_compat_mode: `{report.get('gemini_openai_compat_mode')}`",
        f"- payload_keys: `{report.get('payload_keys')}`",
        f"- omitted_for_gemini: `{report.get('omitted_for_gemini')}`",
        f"- pioneer_used: `{report.get('pioneer_used')}`",
    ]
    if report.get("error"):
        lines.extend(["", f"Error: `{report.get('error')}`"])
    return "\n".join(lines) + "\n"


def _redacted_host(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if not parsed.hostname:
        return "[present]" if url else ""
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}"


def _redact_text(text: str) -> str:
    redacted = redact_secrets(text)
    if not isinstance(redacted, str):
        redacted = str(redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]{12,}", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"sk-[A-Za-z0-9_*.-]{8,}", "[REDACTED]", redacted)
    return redacted


def main() -> int:
    report = run_hermes_toolcall_probe()
    print(
        json.dumps(
            {
                "ok": report.get("ok"),
                "provider": report.get("provider"),
                "model": report.get("model"),
                "sdk_path_used": report.get("sdk_path_used"),
                "toolcall_supported": report.get("toolcall_supported"),
                "tool_calls_count": report.get("tool_calls_count"),
                "tool_name": report.get("tool_name"),
                "json": report.get("json_path"),
                "md": report.get("md_path"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
