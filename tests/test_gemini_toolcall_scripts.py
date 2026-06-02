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
        captured["report_dir"] = Path(report_dir)
        return {
            "ok": True,
            "summary": {"passed_count": 7, "failed_count": 0, "unsupported_claims": 0, "no_tool_fp": 0},
            "rows": [],
        }

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(gemini_smoke, "run_hermes_v2_toolcall_smoke", fake_runner)

    report = gemini_smoke.run_gemini_v2_toolcall_smoke(report_dir=tmp_path)

    assert report["ok"] is True
    assert captured["provider"] == "gemini"
    assert captured["report_dir"] == tmp_path


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
