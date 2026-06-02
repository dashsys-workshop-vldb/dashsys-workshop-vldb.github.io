from __future__ import annotations

from pathlib import Path


class FakeGeminiClient:
    def provider_name(self):
        return "gemini"

    def model_name(self):
        return "gemini-2.5-flash"

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        return {
            "ok": True,
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "sdk_path_used": True,
            "transport": "gemini_sdk",
            "backend_type": "gemini_sdk",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "tool": "submit_probe_result",
                    "name": "submit_probe_result",
                    "arguments": {"route": "DIRECT", "reason": "concept"},
                    "raw_arguments": '{"route":"DIRECT","reason":"concept"}',
                }
            ],
            "finish_reason": "tool_calls",
            "usage": {"total_tokens": 10},
        }


def test_gemini_probe_writes_sanitized_report(monkeypatch, tmp_path):
    from scripts.probe_gemini_toolcall import run_gemini_toolcall_probe

    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    report = run_gemini_toolcall_probe(client=FakeGeminiClient(), report_dir=tmp_path)

    assert report["ok"] is True
    assert report["provider"] == "gemini"
    assert report["toolcall_supported"] is True
    assert report["tool_name"] == "submit_probe_result"
    assert (tmp_path / "gemini_toolcall_probe.json").exists()
    assert "unit-test-gemini-secret" not in (tmp_path / "gemini_toolcall_probe.json").read_text()
    assert "unit-test-gemini-secret" not in (tmp_path / "gemini_toolcall_probe.md").read_text()


def test_gemini_smoke_sets_provider_and_uses_gemini_report_dir(monkeypatch, tmp_path):
    import scripts.run_gemini_v2_toolcall_smoke as gemini_smoke

    captured = {}

    def fake_runner(config=None, *, report_dir=None, probe_runner=None, **kwargs):
        captured["provider"] = __import__("os").environ.get("DASHAGENT_LLM_PROVIDER")
        captured["base_url"] = __import__("os").environ.get("OPENAI_BASE_URL")
        captured["model"] = __import__("os").environ.get("OPENAI_MODEL")
        captured["report_dir"] = Path(report_dir)
        captured["report_name"] = kwargs.get("report_name")
        return {
            "ok": True,
            "summary": {"passed_count": 7, "failed_count": 0, "unsupported_claims": 0, "no_tool_fp": 0},
            "rows": [],
        }

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaUnitTestGeminiSecretValue123456")
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(gemini_smoke, "run_hermes_v2_toolcall_smoke", fake_runner)

    report = gemini_smoke.run_gemini_v2_toolcall_smoke(report_dir=tmp_path)

    assert report["ok"] is True
    assert captured["provider"] == "openai"
    assert captured["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert captured["model"] == "gemini-3.5-flash"
    assert captured["report_dir"] == tmp_path
    assert captured["report_name"] == "gemini_openai_compat_smoke"


def test_gemini_openai_probe_sets_openai_compat_env(monkeypatch, tmp_path):
    import scripts.probe_gemini_openai_toolcall as gemini_openai_probe

    captured = {}

    def fake_hermes_probe(config=None, *, client=None, report_dir=None):
        captured["provider"] = __import__("os").environ.get("DASHAGENT_LLM_PROVIDER")
        captured["base_url"] = __import__("os").environ.get("OPENAI_BASE_URL")
        captured["api_key"] = __import__("os").environ.get("OPENAI_API_KEY")
        captured["model"] = __import__("os").environ.get("OPENAI_MODEL")
        captured["report_dir"] = Path(report_dir)
        return {
            "ok": True,
            "provider": "openai",
            "openai_compat_provider": "gemini",
            "model": "gemini-3.5-flash",
            "sdk_path_used": True,
            "toolcall_supported": True,
            "tool_calls_count": 1,
            "tool_name": "submit_probe_result",
            "finish_reason": "tool_calls",
            "tool_call_warning": None,
            "error": "",
        }

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaUnitTestGeminiSecretValue123456")
    monkeypatch.delenv("DASHAGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(gemini_openai_probe, "run_hermes_toolcall_probe", fake_hermes_probe)
    monkeypatch.setattr(gemini_openai_probe, "load_local_env", lambda *args, **kwargs: {"keys_loaded": ["GEMINI_API_KEY"]})

    report = gemini_openai_probe.run_gemini_openai_toolcall_probe(report_dir=tmp_path)

    assert report["ok"] is True
    assert report["toolcall_supported"] is True
    assert report["tool_calls_count"] == 1
    assert captured["provider"] == "openai"
    assert captured["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert captured["api_key"] == "AIzaUnitTestGeminiSecretValue123456"
    assert captured["model"] == "gemini-3.5-flash"
    assert (tmp_path / "gemini_openai_toolcall_probe.json").exists()
    assert "AIzaUnitTestGeminiSecretValue123456" not in (tmp_path / "gemini_openai_toolcall_probe.json").read_text()


def test_gemini_openai_sdk_payload_debug_reports_payload_key_diff(monkeypatch, tmp_path):
    import scripts.debug_gemini_openai_sdk_payload as debug

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaUnitTestGeminiSecretValue123456")
    monkeypatch.setattr(debug, "load_local_env", lambda *args, **kwargs: {"keys_loaded": ["GEMINI_API_KEY"]})

    def fake_raw_sender(api_key, payload):
        assert api_key == "AIzaUnitTestGeminiSecretValue123456"
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "submit_probe_result", "arguments": '{"route":"DIRECT","reason":"concept"}'}}
                        ]
                    },
                }
            ]
        }

    def fake_sdk_sender(api_key, base_url, model, messages, tools):
        return {
            "ok": False,
            "error": "400 Bad Request Authorization: Bearer AIzaUnitTestGeminiSecretValue123456",
            "tool_calls": [],
            "finish_reason": None,
            "payload_keys": ["model", "messages", "tools", "tool_choice", "temperature"],
        }

    report = debug.run_gemini_openai_sdk_payload_debug(
        report_dir=tmp_path,
        raw_rest_sender=fake_raw_sender,
        sdk_sender=fake_sdk_sender,
    )

    assert report["raw_rest_ok"] is True
    assert report["raw_rest_tool_calls_count"] == 1
    assert report["sdk_ok"] is False
    assert report["sdk_tool_calls_count"] == 0
    assert report["raw_rest_payload_keys"] == ["model", "messages", "tools", "tool_choice"]
    assert report["sdk_payload_keys"] == ["model", "messages", "tools", "tool_choice", "temperature"]
    assert report["payload_key_difference"]["sdk_extra_keys"] == ["temperature"]
    assert "AIzaUnitTestGeminiSecretValue123456" not in (tmp_path / "gemini_openai_sdk_payload_debug.json").read_text()


def test_gemini_vs_qwen_comparison_uses_objective_metrics(tmp_path):
    from scripts.run_gemini_v2_toolcall_smoke import write_gemini_vs_local_qwen_comparison

    gemini = {
        "probe": {"toolcall_supported": True},
        "summary": {
            "passed_count": 7,
            "failed_count": 0,
            "runtime_fact_count": 9,
            "final_semantic_gate_final_failures": 0,
            "final_answer_repair_attempts": 0,
            "unsupported_claims": 0,
            "no_tool_fp": 0,
            "compiled_sql_count": 6,
            "compiled_api_count": 2,
            "sql_calls": 6,
            "api_calls": 2,
        },
    }
    qwen_report = tmp_path / "qwen.json"
    qwen_report.write_text(
        '{"latest_smoke":{"passed_count":7,"failed_count":0,"runtime_fact_count":9,"final_semantic_gate_final_failures":0,"final_answer_repair_attempts":0,"unsupported_claims":0,"no_tool_fp":0,"compiled_sql_count":6,"compiled_api_count":2,"sql_calls":6,"api_calls":2}}',
        encoding="utf-8",
    )

    report = write_gemini_vs_local_qwen_comparison(gemini, report_dir=tmp_path, qwen_report_paths=[qwen_report])

    assert report["gemini"]["passed_count"] == 7
    assert report["local_qwen"]["passed_count"] == 7
    assert "weighted" not in str(report).lower()
    assert (tmp_path / "gemini_vs_local_qwen_comparison.json").exists()


class FakeHTTPError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def test_gemini_openai_compat_debug_forced_tool_choice_not_supported(monkeypatch, tmp_path):
    import scripts.debug_gemini_openai_compat as debug

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaUnitTestGeminiSecretValue123456")
    monkeypatch.setattr(debug, "load_local_env", lambda *args, **kwargs: {"keys_loaded": ["GEMINI_API_KEY"]})

    def fake_runner(api_key, base_url, case, model):
        assert api_key == "AIzaUnitTestGeminiSecretValue123456"
        if case.payload_type == "tool_forced":
            raise FakeHTTPError("Error code: 400 - Bad Request Authorization: Bearer AIzaUnitTestGeminiSecretValue123456", 400)
        tool_calls = []
        finish_reason = "stop"
        content = "hello"
        if case.payload_type == "tool_auto":
            tool_calls = [{"type": "function", "function": {"name": "submit_probe_result", "arguments": '{"route":"DIRECT","reason":"concept"}'}}]
            finish_reason = "tool_calls"
            content = None
        return {"choices": [{"finish_reason": finish_reason, "message": {"content": content, "tool_calls": tool_calls}}]}

    report = debug.run_gemini_openai_compat_debug(report_dir=tmp_path, completion_runner=fake_runner)

    assert report["classification"] == "forced_tool_choice_not_supported"
    assert report["basic_no_tools_any_ok"] is True
    assert report["tool_payload_any_ok"] is True
    assert report["tool_call_any_returned"] is True
    assert report["v2_smoke_should_run"] is False
    assert (tmp_path / "gemini_openai_compat_debug.json").exists()
    assert "AIzaUnitTestGeminiSecretValue123456" not in (tmp_path / "gemini_openai_compat_debug.json").read_text()
    assert "AIzaUnitTestGeminiSecretValue123456" not in (tmp_path / "gemini_openai_compat_debug.md").read_text()


def test_gemini_openai_compat_debug_classifies_endpoint_contract_problem(monkeypatch, tmp_path):
    import scripts.debug_gemini_openai_compat as debug

    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-key")
    monkeypatch.setattr(debug, "load_local_env", lambda *args, **kwargs: {"keys_loaded": []})

    def fake_runner(api_key, base_url, case, model):
        raise FakeHTTPError("Error code: 400 - <html>Bad Request</html>", 400)

    report = debug.run_gemini_openai_compat_debug(report_dir=tmp_path, completion_runner=fake_runner)

    assert report["classification"] == "endpoint_or_base_url_contract_problem"
    assert report["summary"]["total_cells"] == 32
    assert report["summary"]["bad_request_400_cells"] == 32


def test_gemini_openai_compat_debug_classifies_tool_schema_problem(monkeypatch, tmp_path):
    import scripts.debug_gemini_openai_compat as debug

    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-key")
    monkeypatch.setattr(debug, "load_local_env", lambda *args, **kwargs: {"keys_loaded": []})

    def fake_runner(api_key, base_url, case, model):
        if case.payload_type.startswith("tool_"):
            raise FakeHTTPError("Error code: 400 - Bad Request", 400)
        return {"choices": [{"finish_reason": "stop", "message": {"content": "hello", "tool_calls": []}}]}

    report = debug.run_gemini_openai_compat_debug(report_dir=tmp_path, completion_runner=fake_runner)

    assert report["classification"] == "tools_schema_or_tool_choice_problem"
    assert report["basic_no_tools_any_ok"] is True
    assert report["tool_payload_any_ok"] is False
