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
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.probe_hermes_sdk_toolcall import run_hermes_toolcall_probe


REPORT_DIR = ROOT / "outputs" / "reports" / "gemini_toolcall_probe"
REPORT_STEM = "gemini_openai_toolcall_probe"
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_OPENAI_MODEL = "gemini-3.5-flash"


def configure_gemini_openai_compat_env(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_meta = load_local_env(config.project_root)
    gemini_key = os.getenv("GEMINI_API_KEY") or ""
    openai_key = os.getenv("OPENAI_API_KEY") or ""
    if gemini_key:
        os.environ["OPENAI_API_KEY"] = gemini_key
        key_source = "GEMINI_API_KEY"
    elif openai_key:
        key_source = "OPENAI_API_KEY"
    else:
        key_source = "none"
    configured_base_url = os.getenv("OPENAI_BASE_URL") or ""
    configured_model = os.getenv("OPENAI_MODEL") or ""
    os.environ["DASHAGENT_LLM_PROVIDER"] = "openai"
    os.environ["OPENAI_BASE_URL"] = os.getenv("GEMINI_OPENAI_BASE_URL") or (
        configured_base_url if "generativelanguage.googleapis.com" in configured_base_url.lower() else GEMINI_OPENAI_BASE_URL
    )
    os.environ["OPENAI_MODEL"] = os.getenv("GEMINI_OPENAI_MODEL") or (configured_model if "gemini" in configured_model.lower() else GEMINI_OPENAI_MODEL)
    return {
        "env_source": ".env.local" if set(load_meta.get("keys_loaded") or []) & {"GEMINI_API_KEY", "OPENAI_API_KEY"} else ("environment" if key_source != "none" else "none"),
        "key_source": key_source,
        "gemini_api_key_present": bool(gemini_key),
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "openai_base_url_redacted": _redacted_host(os.getenv("OPENAI_BASE_URL") or ""),
        "model": os.getenv("OPENAI_MODEL"),
    }


def run_gemini_openai_toolcall_probe(
    config: Config | None = None,
    *,
    report_dir: Path | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    env = configure_gemini_openai_compat_env(config)
    hermes_report = run_hermes_toolcall_probe(config, client=client, report_dir=report_dir)
    report: dict[str, Any] = {
        "ok": bool(hermes_report.get("ok")),
        "provider_expected": "openai",
        "provider": hermes_report.get("provider"),
        "openai_compat_provider": hermes_report.get("openai_compat_provider") or "gemini",
        "model": hermes_report.get("model") or env.get("model"),
        "gemini_api_key_present": env.get("gemini_api_key_present"),
        "openai_api_key_present": env.get("openai_api_key_present"),
        "env_source": env.get("env_source"),
        "key_source": env.get("key_source"),
        "openai_base_url_redacted": env.get("openai_base_url_redacted"),
        "sdk_path_used": bool(hermes_report.get("sdk_path_used")),
        "toolcall_supported": bool(hermes_report.get("toolcall_supported")),
        "tool_calls_count": int(hermes_report.get("tool_calls_count") or 0),
        "tool_name": hermes_report.get("tool_name"),
        "finish_reason": hermes_report.get("finish_reason"),
        "tool_call_warning": hermes_report.get("tool_call_warning"),
        "error": _redact_text(str(hermes_report.get("error") or ""))[:500],
        "hermes_probe_json": hermes_report.get("json_path"),
        "hermes_probe_md": hermes_report.get("md_path"),
        "pioneer_used": bool(hermes_report.get("pioneer_used")),
    }
    report["ok"] = bool(report["toolcall_supported"])
    return _write_report(report_dir, report)


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    if not isinstance(safe_report, dict):
        safe_report = report
    elif report.get("model"):
        safe_report["model"] = report.get("model")
    json_path = report_dir / f"{REPORT_STEM}.json"
    md_path = report_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(safe_report), encoding="utf-8")
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    return safe_report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gemini OpenAI-Compatible Toolcall Probe",
        "",
        "Uses the OpenAI SDK-compatible Gemini endpoint and the minimal submit_probe_result tool schema.",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- provider: `{report.get('provider')}`",
        f"- openai_compat_provider: `{report.get('openai_compat_provider')}`",
        f"- model: `{report.get('model')}`",
        f"- GEMINI_API_KEY present: `{report.get('gemini_api_key_present')}`",
        f"- OPENAI_API_KEY present: `{report.get('openai_api_key_present')}`",
        f"- key_source: `{report.get('key_source')}`",
        f"- OPENAI_BASE_URL host: `{report.get('openai_base_url_redacted')}`",
        f"- sdk_path_used: `{report.get('sdk_path_used')}`",
        f"- toolcall_supported: `{report.get('toolcall_supported')}`",
        f"- tool_calls_count: `{report.get('tool_calls_count')}`",
        f"- tool_name: `{report.get('tool_name')}`",
        f"- finish_reason: `{report.get('finish_reason')}`",
        f"- tool_call_warning: `{report.get('tool_call_warning')}`",
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
    redacted = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[REDACTED]", redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]{12,}", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted.replace(os.getenv("GEMINI_API_KEY") or "\0", "[REDACTED]")


def main() -> int:
    report = run_gemini_openai_toolcall_probe()
    print(
        json.dumps(
            {
                "ok": report.get("ok"),
                "provider": report.get("provider"),
                "openai_compat_provider": report.get("openai_compat_provider"),
                "model": report.get("model"),
                "sdk_path_used": report.get("sdk_path_used"),
                "toolcall_supported": report.get("toolcall_supported"),
                "tool_calls_count": report.get("tool_calls_count"),
                "tool_name": report.get("tool_name"),
                "finish_reason": report.get("finish_reason"),
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
