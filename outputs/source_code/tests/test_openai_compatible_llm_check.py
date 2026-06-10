from __future__ import annotations

import json
from pathlib import Path

from scripts import check_llm_sdk_backend
from scripts import check_openai_compatible_llm as check
from scripts.run_llm_baseline_eval import build_llm_baseline_report


def _clear_openai_env(monkeypatch):
    for key in [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "LLM_PROVIDER",
    ]:
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
        base_url = "https://photos-hewlett-safely-friends.trycloudflare.com/v1"

        def provider_name(self):
            return "openai"

        def model_name(self):
            return "qwen2.5-32b-instruct"

        def available(self):
            return True

        def generate_messages(self, *args, **kwargs):
            return {
                "ok": False,
                "transport": "openai_sdk",
                "backend_type": "openai_sdk",
                "sdk_path_used": True,
                "error": "Authorization" + ": " + "Bearer " + "unit-test-qwen-secret endpoint unavailable",
                "tool_calls": [],
            }

    monkeypatch.setattr(check_llm_sdk_backend, "get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(check_llm_sdk_backend, "OpenAI", object())

    report = check.run_openai_compatible_llm_check(tiny_project)
    text = json.dumps(report)

    assert report["ok"] is False
    assert "endpoint_unavailable" in report["failure_categories"]
    assert report["deprecated_wrapper"] is True
    assert report["delegates_to"] == "scripts/check_llm_sdk_backend.py"
    assert report["sdk_path_used"] is True
    assert "unit-test-qwen-secret" not in text
    assert "Authorization" + ": " + "Bearer " + "unit-test" not in text


def test_llm_baseline_report_marks_results_shadow_only(monkeypatch, tiny_project):
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "llm_sdk_backend_check.json").write_text(
        json.dumps({"ok": True, "provider": "openai", "provider_type": "openai_compatible", "backend_type": "openai_sdk", "tool_calling_supported": True}),
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

    report = build_llm_baseline_report(tiny_project, payload)

    assert report["framework"] == "generic_sdk_llm_baseline"
    assert report["provider_type"] == "openai_compatible"
    assert report["backend_type"] == "openai_sdk"
    assert report["sdk_path_used"] is True
    assert report["model"] == "qwen2.5-32b-instruct"
    assert report["tool_calling_supported"] is True
    assert report["promotion_status"] == "shadow_only"
    assert report["recommendation"] == "keep_shadow_only"
    assert report["deterministic_sql_first_api_verify"]["avg_final_score"] == 0.6491
    assert "Qwen LLM Baseline" not in json.dumps(report)


def test_generic_sdk_backend_check_handles_missing_key(monkeypatch, tiny_project):
    _clear_openai_env(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    report = check_llm_sdk_backend.run_llm_sdk_backend_check(tiny_project)

    assert report["ok"] is False
    assert report["framework"] == "generic_sdk_llm_baseline"
    assert "missing_openai_api_key" in report["failure_categories"]
    assert "Authorization" + ": " + "Bearer" not in json.dumps(report)


def test_openai_compatible_check_is_deprecated_sdk_wrapper():
    source = Path(check.__file__).read_text(encoding="utf-8")
    assert "run_llm_sdk_backend_check" in source
    assert "OpenAI(" not in source
    assert "/chat/completions" not in source
