from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashagent.llm_client import AnthropicLLMClient, OpenAILLMClient
from dashagent.llm_tool_agent import (
    _allowed_tool_schemas_for_route,
    _baseline_tool_schemas,
    _compact_llm_tool_result_summary,
    _controller_backend_answer_complete,
    _tool_result_message,
    run_optimized_llm_controller_agent,
)
from dashagent.prompt_router import API_ONLY, API_REQUIRED, API_SKIP, LLM_DIRECT, LOCAL_DB_ONLY, PromptRouteDecision, SQL_PLUS_API
from scripts.run_sdk_tool_calling_efficiency_promotion import run_sdk_tool_calling_efficiency_promotion


class CapturingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "fake-model"

    def generate(self, system_prompt, user_prompt, tools=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "tools": tools})
        return {"ok": True, "content": "rewritten answer", "usage": {"total_tokens": 10}}

    def generate_messages(self, messages, tools=None, tool_choice=None):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return {"ok": True, "content": "rewritten answer", "tool_calls": [], "usage": {"total_tokens": 10}}


def _route(mode: str, *, api_policy: str = API_SKIP, requires_database: bool = True, requires_api: bool = False) -> PromptRouteDecision:
    return PromptRouteDecision(
        mode=mode,
        reason="unit-test",
        confidence=0.9,
        requires_database=requires_database,
        requires_api=requires_api,
        api_policy=api_policy,
    )


def test_compact_tool_schema_preserves_contract_and_reduces_descriptions():
    tools = _baseline_tool_schemas()
    by_name = {tool["function"]["name"]: tool for tool in tools}

    assert set(by_name) == {"execute_sql", "call_api"}
    assert by_name["execute_sql"]["function"]["parameters"]["required"] == ["sql"]
    assert by_name["call_api"]["function"]["parameters"]["required"] == ["method", "url"]
    assert by_name["execute_sql"]["function"]["parameters"]["properties"]["sql"]["type"] == "string"
    assert by_name["call_api"]["function"]["parameters"]["properties"]["method"]["type"] == "string"
    assert len(by_name["execute_sql"]["function"]["description"]) <= 48
    assert len(by_name["call_api"]["function"]["description"]) <= 48


def test_anthropic_conversion_accepts_compact_tool_schema(monkeypatch):
    captured = {}

    class FakeMessage:
        def model_dump(self):
            return {"stop_reason": "stop", "content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 1, "output_tokens": 1}}

    class FakeMessages:
        def create(self, **payload):
            captured["payload"] = payload
            return FakeMessage()

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr("dashagent.llm_client.Anthropic", FakeAnthropic)
    client = AnthropicLLMClient(api_key="unit-test-anthropic-key")
    result = client.generate_messages([{"role": "user", "content": "count"}], tools=_baseline_tool_schemas())

    assert result["ok"] is True
    assert [tool["name"] for tool in captured["payload"]["tools"]] == ["execute_sql", "call_api"]
    assert captured["payload"]["tools"][0]["input_schema"]["required"] == ["sql"]


def test_openai_payload_can_disable_parallel_tool_calls(monkeypatch):
    captured = {}

    class FakeCompletion:
        def model_dump(self):
            return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}], "usage": {"total_tokens": 3}}

    class FakeCompletions:
        def create(self, **payload):
            captured["payload"] = payload
            return FakeCompletion()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = OpenAILLMClient(api_key="unit-test-openai-key")
    result = client.generate_messages(
        [{"role": "user", "content": "count"}],
        tools=_baseline_tool_schemas(),
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    assert result["ok"] is True
    assert captured["payload"]["parallel_tool_calls"] is False


def test_allowed_tools_by_prompt_type_keeps_api_required_safe():
    tools = _baseline_tool_schemas()

    sql_only = _allowed_tool_schemas_for_route(tools, _route(LOCAL_DB_ONLY, api_policy=API_SKIP, requires_api=False))
    api_only = _allowed_tool_schemas_for_route(tools, _route(API_ONLY, api_policy=API_REQUIRED, requires_database=False, requires_api=True))
    ambiguous = _allowed_tool_schemas_for_route(tools, _route(SQL_PLUS_API, api_policy="API_OPTIONAL", requires_api=True))
    direct = _allowed_tool_schemas_for_route(tools, _route(LLM_DIRECT, api_policy=API_SKIP, requires_database=False, requires_api=False))

    assert [tool["function"]["name"] for tool in sql_only] == ["execute_sql"]
    assert [tool["function"]["name"] for tool in api_only] == ["call_api"]
    assert [tool["function"]["name"] for tool in ambiguous] == ["execute_sql", "call_api"]
    assert direct == []


def test_compact_tool_result_summary_preserves_evidence_and_redacts_values():
    executed = {
        "tool_name": "execute_sql",
        "executed": True,
        "validation_ok": True,
        "result_preview": {
            "ok": True,
            "row_count": 2,
            "rows_preview": [
                {"name": "Audience One", "status": "active", "updated_at": "2026-01-01T00:00:00Z", "token": "sk-" + "unitsecret123456"},
                {"name": "Audience Two", "status": "inactive"},
            ],
        },
    }

    summary = _compact_llm_tool_result_summary(executed)
    message = _tool_result_message({"id": "call_1"}, executed)
    payload = json.loads(message["content"])

    assert summary["row_count"] == 2
    assert {"name", "status", "updated_at"} <= set(summary["key_fields"])
    assert "sk-" + "unitsecret" not in json.dumps(summary)
    assert payload["row_count"] == 2
    assert "result_preview" not in payload


def test_controller_backend_answer_complete_skips_llm_rewrite(monkeypatch, tiny_project):
    backend = {
        "final_answer": "The database count is 2.",
        "trajectory": {},
        "tool_results_summary": {},
        "diagnostics": {"tool_call_count": 1, "estimated_tokens": 20, "runtime": 0.01},
        "tool_results": [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"count": 2}]}}],
    }
    monkeypatch.setattr("dashagent.llm_tool_agent.run_data_answer_tool", lambda *args, **kwargs: backend)
    client = CapturingClient()

    result = run_optimized_llm_controller_agent("How many audiences are there?", config=tiny_project, llm_client=client)

    assert result["backend_used"] is True
    assert result["real_llm_used"] is False
    assert result["final_answer"] == "The database count is 2."
    assert result["rewrite_skipped_reason"] == "backend_answer_complete"
    assert client.calls == []
    assert _controller_backend_answer_complete("How many audiences are there?", backend)["complete"] is True


def test_controller_incomplete_backend_answer_can_still_rewrite(monkeypatch, tiny_project):
    backend = {
        "final_answer": "I found local evidence.",
        "trajectory": {},
        "tool_results_summary": {},
        "diagnostics": {"tool_call_count": 1, "estimated_tokens": 20, "runtime": 0.01},
        "tool_results": [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"count": 2}]}}],
    }
    monkeypatch.setattr("dashagent.llm_tool_agent.run_data_answer_tool", lambda *args, **kwargs: backend)
    client = CapturingClient()

    result = run_optimized_llm_controller_agent("How many audiences are there?", config=tiny_project, llm_client=client)

    assert result["real_llm_used"] is True
    assert result["final_answer"]
    assert client.calls


def test_efficiency_promotion_reports_exist_and_do_not_write_official_artifacts(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "system_summary.json").write_text(
        json.dumps(
            {
                "preferred_strategy": "SQL_FIRST_API_VERIFY",
                "packaged_strict_score": 0.6553,
                "hidden_style": {"passed": 48, "total": 48},
                "final_submission_ready": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "sdk_usage_audit.json").write_text(json.dumps({"summary": {"runtime_llm_direct_http_hits": 0}}), encoding="utf-8")
    (reports / "correctness_efficiency_scorecard.json").write_text(
        json.dumps(
            {
                "baseline": {
                    "tool_calls": 2,
                    "total_tokens": 100,
                    "wall_time_seconds": 1.0,
                    "end_to_end_time_seconds": 1.5,
                },
                "variants": [
                    {
                        "variant_id": "combined_safe_tool_policy",
                        "efficiency": {
                            "tool_calls": 1,
                            "tool_calls_delta": -1,
                            "total_tokens": 80,
                            "total_tokens_delta": -20,
                            "wall_time_seconds": 0.8,
                            "wall_time_delta": -0.2,
                            "end_to_end_time_seconds": 1.2,
                            "end_to_end_time_delta": -0.3,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(json.dumps({"summary": {"by_strategy": {}}}), encoding="utf-8")

    payload = run_sdk_tool_calling_efficiency_promotion(tiny_project)

    for stem in [
        "sdk_tool_calling_promotion_preflight",
        "sdk_tool_calling_promotion_plan",
        "sdk_tool_calling_efficiency_promotion_decision",
    ]:
        assert (reports / f"{stem}.json").exists()
        assert (reports / f"{stem}.md").exists()

    assert payload["preflight"]["selected_candidate"] == "combined_safe_tool_policy"
    assert payload["preflight"]["runtime_change_requested"] is True
    assert payload["plan"]["packaged_strategy_changed"] is False
    assert payload["decision"]["final_submission_format_changed"] is False
    assert payload["decision"]["final_submission_ready_before"] is True
    assert payload["decision"]["final_submission_ready_after"] is True
    assert not (tiny_project.outputs_dir / "final_submission").exists()
    assert payload["decision"]["direct_http_hits"] == 0
    assert payload["decision"]["direct_http_hits_before"] == 0
    assert payload["decision"]["direct_http_hits_after"] == 0
    assert payload["decision"]["tool_call_count_before_after"]["delta"] == -1
    assert payload["decision"]["token_count_before_after"]["delta"] == -20
    assert payload["decision"]["wall_time_before_after"]["delta"] == -0.2
    assert payload["decision"]["end_to_end_runtime_before_after"]["delta"] == -0.3
    combined = "\n".join((reports / f"{stem}.json").read_text(encoding="utf-8") for stem in [
        "sdk_tool_calling_promotion_preflight",
        "sdk_tool_calling_promotion_plan",
        "sdk_tool_calling_efficiency_promotion_decision",
    ])
    assert "Authorization" not in combined
    assert "Bearer " not in combined
    assert "[MASKED_PREFIX]" not in combined
