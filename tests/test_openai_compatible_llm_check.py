from __future__ import annotations

import json

from scripts import check_openai_compatible_llm as check
from scripts.run_llm_baseline_eval import build_qwen_report


def _clear_openai_env(monkeypatch):
    for key in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_USE_REQUESTS_FALLBACK"]:
        monkeypatch.delenv(key, raising=False)


def test_openai_compatible_check_handles_missing_key_cleanly(monkeypatch, tiny_project):
    _clear_openai_env(monkeypatch)

    report = check.run_openai_compatible_llm_check(tiny_project)
    text = json.dumps(report)

    assert report["ok"] is False
    assert report["key_visible"] is False
    assert "missing_openai_api_key" in report["failure_categories"]
    assert "Authorization" + ": " + "Bearer" not in text


def test_openai_compatible_check_reports_endpoint_unavailable_without_leaking_key(monkeypatch, tiny_project):
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-qwen-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def generate_messages(self, *args, **kwargs):
            return {
                "ok": False,
                "transport": "openai_sdk",
                "error": "Authorization" + ": " + "Bearer unit-test-qwen-secret endpoint unavailable",
                "tool_calls": [],
            }

    monkeypatch.setattr(check, "OpenAILLMClient", FakeClient)
    monkeypatch.setattr(check, "OpenAI", None)

    report = check.run_openai_compatible_llm_check(tiny_project)
    text = json.dumps(report)

    assert report["ok"] is False
    assert "endpoint_unavailable" in report["failure_categories"]
    assert "unit-test-qwen-secret" not in text
    assert "Authorization" + ": " + "Bearer unit-test" not in text


def test_qwen_report_marks_results_shadow_only(monkeypatch, tiny_project):
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "openai_compatible_llm_check.json").write_text(
        json.dumps({"ok": True, "tool_calling_supported": True}),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "final_score": 0.6491,
                        "correctness_score": 0.6743,
                        "answer_score": 0.5,
                        "tool_call_count": 1.45,
                        "estimated_tokens": 831,
                        "runtime": 0.011,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "skipped": False,
        "systems": ["RAW_REAL_LLM_TWO_TOOLS_BASELINE"],
        "rows": [
            {
                "system": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
                "valid_agent_run": True,
                "answer_score": 0.4,
                "tool_call_count": 2,
                "prompt_context_tokens": 100,
                "runtime": 0.5,
            }
        ],
    }

    report = build_qwen_report(tiny_project, payload)

    assert report["provider"] == "openai_compatible_qwen"
    assert report["tool_calling_supported"] is True
    assert report["promotion_status"] == "shadow_only"
    assert report["recommendation"] == "keep_shadow_only"
    assert report["deterministic_sql_first_api_verify"]["avg_final_score"] == 0.6491
