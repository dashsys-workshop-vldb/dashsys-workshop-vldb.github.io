from __future__ import annotations

import json
from pathlib import Path

from scripts.probe_hermes_sdk_toolcall import run_hermes_toolcall_probe


class FakeProbeClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return "hermes-test-model"

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice, "parallel_tool_calls": parallel_tool_calls})
        return self.response


class FakePioneerClient(FakeProbeClient):
    def provider_name(self) -> str:
        return "pioneer_chat"


def test_hermes_toolcall_probe_accepts_native_tool_call(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("scripts.probe_hermes_sdk_toolcall.load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setenv("OPENAI_API_KEY", "unit-pioneer-key")
    monkeypatch.setenv("OPENAI_MODEL", "hermes-qianwan")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://senior.example/v1")
    client = FakeProbeClient(
        {
            "ok": True,
            "provider": "openai",
            "model": "hermes-qianwan",
            "sdk_path_used": True,
            "finish_reason": "tool_calls",
            "tool_calls": [{"name": "submit_probe_result", "arguments": {"route": "DIRECT", "reason": "concept"}}],
        }
    )

    report = run_hermes_toolcall_probe(client=client, report_dir=tmp_path)

    assert report["ok"] is True
    assert report["toolcall_supported"] is True
    assert report["tool_calls_count"] == 1
    assert report["tool_name"] == "submit_probe_result"
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_probe_result"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_probe_result"
    assert client.calls[0]["parallel_tool_calls"] is False


def test_hermes_toolcall_probe_uses_minimal_gemini_openai_schema(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("scripts.probe_hermes_sdk_toolcall.load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setenv("OPENAI_API_KEY", "unit-gemini-key")
    monkeypatch.setenv("OPENAI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    client = FakeProbeClient(
        {
            "ok": True,
            "provider": "openai",
            "model": "gemini-3.5-flash",
            "sdk_path_used": True,
            "finish_reason": "tool_calls",
            "tool_calls": [{"name": "submit_probe_result", "arguments": {"route": "DIRECT", "reason": "concept"}}],
        }
    )

    report = run_hermes_toolcall_probe(client=client, report_dir=tmp_path)

    parameters = client.calls[0]["tools"][0]["function"]["parameters"]
    assert report["ok"] is True
    assert report["openai_compat_provider"] == "gemini"
    assert report["toolcall_supported"] is True
    assert client.calls[0]["messages"] == [{"role": "user", "content": "Classify: What is a schema? You must call the tool."}]
    assert client.calls[0]["tools"][0]["function"]["description"] == "Submit classification"
    assert parameters == {
        "type": "object",
        "properties": {
            "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
            "reason": {"type": "string"},
        },
        "required": ["route", "reason"],
    }
    assert "additionalProperties" not in parameters
    assert client.calls[0]["tool_choice"] == "auto"
    assert client.calls[0]["parallel_tool_calls"] is None


def test_hermes_toolcall_probe_rejects_content_only_response(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("scripts.probe_hermes_sdk_toolcall.load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setenv("OPENAI_API_KEY", "unit-pioneer-key")
    client = FakeProbeClient(
        {
            "ok": True,
            "provider": "openai",
            "model": "hermes-qianwan",
            "sdk_path_used": True,
            "finish_reason": "stop",
            "content": '{"route":"DIRECT"}',
            "tool_calls": [],
        }
    )

    report = run_hermes_toolcall_probe(client=client, report_dir=tmp_path)

    assert report["ok"] is False
    assert report["toolcall_supported"] is False
    assert "without native SDK tool_calls" in report["error"]


def test_hermes_toolcall_probe_redacts_key_and_does_not_use_pioneer(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("scripts.probe_hermes_sdk_toolcall.load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setenv("OPENAI_API_KEY", "unit-pioneer-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://user:secret@senior.example/v1")
    report = run_hermes_toolcall_probe(client=FakePioneerClient({"ok": True}), report_dir=tmp_path)

    assert report["ok"] is False
    assert report["pioneer_used"] is True
    text = (Path(tmp_path) / "hermes_toolcall_probe.json").read_text(encoding="utf-8")
    assert "sk-test-secret" not in text
    assert "Authorization" not in text
    assert "pioneer" in text


def test_hermes_toolcall_probe_report_files_are_json_and_md(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("scripts.probe_hermes_sdk_toolcall.load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setenv("OPENAI_API_KEY", "unit-pioneer-key")
    client = FakeProbeClient(
        {
            "ok": True,
            "provider": "openai",
            "model": "hermes-qianwan",
            "sdk_path_used": True,
            "finish_reason": "tool_calls",
            "tool_calls": [{"name": "submit_probe_result", "arguments": {"route": "DIRECT", "reason": "concept"}}],
        }
    )

    report = run_hermes_toolcall_probe(client=client, report_dir=tmp_path)

    assert Path(report["json_path"]).exists()
    assert Path(report["md_path"]).exists()
    payload = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
    assert payload["toolcall_supported"] is True
