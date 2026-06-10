#!/usr/bin/env python
from __future__ import annotations

import json
import http.client
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import OpenAILLMClient
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.probe_gemini_openai_toolcall import configure_gemini_openai_compat_env
from scripts.probe_hermes_sdk_toolcall import PROBE_TOOL_NAME, probe_tool_schema


REPORT_DIR = ROOT / "outputs" / "reports" / "gemini_toolcall_probe"
REPORT_STEM = "gemini_openai_sdk_payload_debug"

RawRestSender = Callable[[str, dict[str, Any]], dict[str, Any]]
SdkSender = Callable[[str, str, str, list[dict[str, str]], list[dict[str, Any]]], dict[str, Any]]


def run_gemini_openai_sdk_payload_debug(
    config: Config | None = None,
    *,
    report_dir: Path | None = None,
    raw_rest_sender: RawRestSender | None = None,
    sdk_sender: SdkSender | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    configure_gemini_openai_compat_env(config)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    base_url = os.getenv("OPENAI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
    model = os.getenv("OPENAI_MODEL") or "gemini-3.5-flash"
    messages = [{"role": "user", "content": "Classify: What is a schema? You must call the tool."}]
    tools = [probe_tool_schema("gemini")]
    raw_payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }

    raw_sender = raw_rest_sender or (lambda key, payload: _send_raw_rest(key, payload, base_url=base_url))
    sdk_call = sdk_sender or _send_sdk
    raw_result = _call_raw(raw_sender, api_key, raw_payload)
    sdk_result = _call_sdk(sdk_call, api_key, base_url, model, messages, tools)
    raw_payload_keys = list(raw_payload.keys())
    sdk_payload_keys = list(sdk_result.get("payload_keys") or [])
    report: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "base_url": _redacted_base_url(base_url),
        "model": model,
        "api_key_present": bool(api_key),
        "raw_rest_ok": raw_result["ok"],
        "raw_rest_tool_calls_count": raw_result["tool_calls_count"],
        "raw_rest_finish_reason": raw_result.get("finish_reason"),
        "raw_rest_error": raw_result.get("error") or "",
        "sdk_ok": sdk_result["ok"],
        "sdk_tool_calls_count": sdk_result["tool_calls_count"],
        "sdk_finish_reason": sdk_result.get("finish_reason"),
        "sdk_error": sdk_result.get("error") or "",
        "raw_rest_payload_keys": raw_payload_keys,
        "sdk_payload_keys": sdk_payload_keys,
        "payload_key_difference": _payload_key_difference(raw_payload_keys, sdk_payload_keys),
        "raw_rest_payload_shape": _payload_shape(raw_payload),
        "sdk_gemini_openai_compat_mode": sdk_result.get("gemini_openai_compat_mode"),
        "sdk_omitted_for_gemini": sdk_result.get("omitted_for_gemini") or [],
    }
    return _write_report(report_dir, report)


def _call_raw(sender: RawRestSender, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not api_key:
        return {"ok": False, "tool_calls_count": 0, "finish_reason": None, "error": "OPENAI_API_KEY/GEMINI_API_KEY is not set"}
    try:
        body = sender(api_key, payload)
    except Exception as exc:
        return {"ok": False, "tool_calls_count": 0, "finish_reason": None, "error": _redact_text(str(exc))[:500]}
    finish_reason = _finish_reason(body)
    count = _tool_calls_count(body)
    return {"ok": count > 0, "tool_calls_count": count, "finish_reason": finish_reason, "error": ""}


def _call_sdk(
    sender: SdkSender,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    if not api_key:
        return {"ok": False, "tool_calls_count": 0, "finish_reason": None, "error": "OPENAI_API_KEY/GEMINI_API_KEY is not set", "payload_keys": []}
    try:
        result = sender(api_key, base_url, model, messages, tools)
    except Exception as exc:
        return {"ok": False, "tool_calls_count": 0, "finish_reason": None, "error": _redact_text(str(exc))[:500], "payload_keys": []}
    tool_calls = result.get("tool_calls") if isinstance(result.get("tool_calls"), list) else []
    return {
        "ok": bool(result.get("ok")) and len(tool_calls) > 0,
        "tool_calls_count": len(tool_calls),
        "finish_reason": result.get("finish_reason"),
        "error": _redact_text(str(result.get("error") or result.get("reason") or ""))[:500],
        "payload_keys": result.get("payload_keys") or [],
        "gemini_openai_compat_mode": result.get("gemini_openai_compat_mode"),
        "omitted_for_gemini": result.get("omitted_for_gemini") or [],
    }


def _send_raw_rest(api_key: str, payload: dict[str, Any], *, base_url: str) -> dict[str, Any]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "generativelanguage.googleapis.com"
    path = (parsed.path or "/v1beta/openai").rstrip("/") + "/" + "chat" + "/" + "completions"
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    connection = http.client.HTTPSConnection(host, timeout=30)
    connection.request(
        "POST",
        path,
        body=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    response = connection.getresponse()
    text = response.read().decode("utf-8", errors="replace")
    if response.status >= 400:
        raise RuntimeError(f"HTTP {response.status}: {_redact_text(text)[:300]}")
    return json.loads(text)


def _send_sdk(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    client = OpenAILLMClient(api_key=api_key, base_url=base_url, model=model, timeout_seconds=30)
    return client.generate_messages(messages, tools=tools, tool_choice="auto")


def _finish_reason(body: dict[str, Any]) -> Any:
    choices = body.get("choices") if isinstance(body.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    return first.get("finish_reason")


def _tool_calls_count(body: dict[str, Any]) -> int:
    choices = body.get("choices") if isinstance(body.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
    return len(tool_calls)


def _payload_key_difference(raw_keys: list[str], sdk_keys: list[str]) -> dict[str, Any]:
    return {
        "sdk_missing_keys": [key for key in raw_keys if key not in sdk_keys],
        "sdk_extra_keys": [key for key in sdk_keys if key not in raw_keys],
        "same_order": raw_keys == sdk_keys,
    }


def _payload_shape(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "keys": list(payload.keys()),
        "message_count": len(payload.get("messages") or []),
        "tool_count": len(payload.get("tools") or []),
        "tool_choice": payload.get("tool_choice"),
        "tool_names": [
            str((tool.get("function") or {}).get("name"))
            for tool in payload.get("tools") or []
            if isinstance(tool, dict)
        ],
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(report)
    if not isinstance(safe, dict):
        safe = report
    if report.get("model"):
        safe["model"] = report.get("model")
    if report.get("base_url"):
        safe["base_url"] = report.get("base_url")
    json_path = report_dir / f"{REPORT_STEM}.json"
    md_path = report_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(safe), encoding="utf-8")
    safe["json_path"] = str(json_path)
    safe["md_path"] = str(md_path)
    return safe


def _markdown(report: dict[str, Any]) -> str:
    diff = report.get("payload_key_difference") or {}
    lines = [
        "# Gemini OpenAI SDK Payload Debug",
        "",
        "Compares the known-working raw REST payload shape against the OpenAI SDK payload shape.",
        "",
        f"- base_url: `{report.get('base_url')}`",
        f"- model: `{report.get('model')}`",
        f"- api_key_present: `{report.get('api_key_present')}`",
        f"- raw_rest_ok: `{report.get('raw_rest_ok')}`",
        f"- raw_rest_tool_calls_count: `{report.get('raw_rest_tool_calls_count')}`",
        f"- raw_rest_finish_reason: `{report.get('raw_rest_finish_reason')}`",
        f"- sdk_ok: `{report.get('sdk_ok')}`",
        f"- sdk_tool_calls_count: `{report.get('sdk_tool_calls_count')}`",
        f"- sdk_finish_reason: `{report.get('sdk_finish_reason')}`",
        f"- raw_rest_payload_keys: `{report.get('raw_rest_payload_keys')}`",
        f"- sdk_payload_keys: `{report.get('sdk_payload_keys')}`",
        f"- sdk_missing_keys: `{diff.get('sdk_missing_keys')}`",
        f"- sdk_extra_keys: `{diff.get('sdk_extra_keys')}`",
        f"- same_order: `{diff.get('same_order')}`",
        f"- sdk_gemini_openai_compat_mode: `{report.get('sdk_gemini_openai_compat_mode')}`",
        f"- sdk_omitted_for_gemini: `{report.get('sdk_omitted_for_gemini')}`",
    ]
    if report.get("raw_rest_error"):
        lines.extend(["", f"Raw REST error: `{report.get('raw_rest_error')}`"])
    if report.get("sdk_error"):
        lines.extend(["", f"SDK error: `{report.get('sdk_error')}`"])
    return "\n".join(lines) + "\n"


def _redacted_base_url(base_url: str) -> str:
    return str(base_url or "").split("?", 1)[0]


def _redact_text(text: str) -> str:
    redacted = redact_secrets(text)
    if not isinstance(redacted, str):
        redacted = str(redacted)
    redacted = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[REDACTED]", redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]{12,}", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted.replace(os.getenv("GEMINI_API_KEY") or "\0", "[REDACTED]")


def main() -> int:
    report = run_gemini_openai_sdk_payload_debug()
    print(
        json.dumps(
            {
                "raw_rest_ok": report.get("raw_rest_ok"),
                "raw_rest_tool_calls_count": report.get("raw_rest_tool_calls_count"),
                "sdk_ok": report.get("sdk_ok"),
                "sdk_tool_calls_count": report.get("sdk_tool_calls_count"),
                "payload_key_difference": report.get("payload_key_difference"),
                "json": report.get("json_path"),
                "md": report.get("md_path"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.get("raw_rest_ok") and report.get("sdk_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
