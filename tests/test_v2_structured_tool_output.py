from __future__ import annotations

import json

from dashagent.llm_final_answer_composer import compose_llm_final_answer
from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.pass_graph_gate import PassGraphGate


class ToolCallClient:
    def __init__(self, tool_name: str, arguments: dict) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake_tool_provider"

    def model_name(self) -> str:
        return "fake_tool_model"

    def generate(self, system_prompt, user_prompt, tools=None):
        return self.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            tools=tools,
            tool_choice="required" if tools else None,
        )

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"tools": tools, "tool_choice": tool_choice, "messages": messages})
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": "",
            "tool_calls": [
                {
                    "name": self.tool_name,
                    "tool": self.tool_name,
                    "arguments": self.arguments,
                    "raw_arguments": json.dumps(self.arguments),
                }
            ],
        }


class ContentOnlyPlannerClient:
    def __init__(self, responses: list[str], *, provider: str = "pioneer_chat", model: str = "weak-model") -> None:
        self.responses = list(responses)
        self.provider = provider
        self.model = model
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return self.provider

    def model_name(self) -> str:
        return self.model

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"tools": tools, "tool_choice": tool_choice, "messages": messages})
        if not self.responses:
            raise AssertionError("Fake planner client called more times than expected")
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": self.responses.pop(0),
            "tool_calls": [],
            "finish_reason": "stop",
        }

    def generate(self, system_prompt, user_prompt, tools=None):
        return self.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            tools=tools,
            tool_choice="auto" if tools else None,
        )


class TimeoutPlannerClient(ContentOnlyPlannerClient):
    def __init__(self) -> None:
        super().__init__([])

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"tools": tools, "tool_choice": tool_choice, "messages": messages})
        raise TimeoutError("unit timeout")


def _planner_json(**overrides) -> str:
    payload = {
        "route": "EVIDENCE_PIPELINE",
        "evidence_order": "SQL_FIRST",
        "direct_answer": None,
        "passes": [
            {
                "pass_id": "pass_1",
                "subtask": "Count schema records.",
                "path": "SQL",
                "can_run_parallel": True,
                "depends_on": [],
                "sql": {"query": "SELECT COUNT(*) AS count FROM schemas", "params": []},
                "api_request": None,
                "expected_result": "schema count",
            }
        ],
        "aggregation_instruction": "Answer with the count.",
        "reason": "data request",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_llm_unified_planner_prefers_sdk_toolcall_structured_output(monkeypatch):
    client = ToolCallClient(
        "submit_v2_plan",
        {
            "route": "LLM_DIRECT",
            "evidence_order": "NO_EVIDENCE",
            "direct_answer": "A schema defines data structure.",
            "passes": [],
            "aggregation_instruction": None,
            "reason": "pure concept",
        },
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.direct_answer == "A schema defines data structure."
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_v2_plan"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_v2_plan"


def test_pioneer_planner_uses_json_content_fallback_without_toolcall(monkeypatch):
    client = ContentOnlyPlannerClient([_planner_json()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1
    assert plan.diagnostics["planner_json_fallback_used"] is True
    assert plan.diagnostics["planner_toolcall_attempted"] is False
    assert client.calls[0]["tools"] is None


def test_planner_json_fallback_extracts_code_fenced_json(monkeypatch):
    client = ContentOnlyPlannerClient(["```json\n" + _planner_json() + "\n```"])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.passes[0].sql.query == "SELECT COUNT(*) AS count FROM schemas"
    assert plan.diagnostics["planner_success"] is True


def test_malformed_planner_json_triggers_one_repair(monkeypatch):
    client = ContentOnlyPlannerClient(["not-json", _planner_json(reason="repaired")])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.reason == "repaired"
    assert len(client.calls) == 2
    assert plan.diagnostics["planner_repair_attempted"] is True
    assert plan.diagnostics["planner_success"] is True


def test_lack_of_toolcall_is_not_fatal_when_content_json_is_valid(monkeypatch):
    client = ContentOnlyPlannerClient([_planner_json()], provider="fake_no_tool_provider")
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1
    assert plan.parse_error is False


def test_planner_fails_closed_without_backend_created_semantic_plan(monkeypatch):
    client = ContentOnlyPlannerClient(["bad json", "still bad"])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.passes == []
    assert plan.sql is None
    assert plan.api_request is None
    assert plan.parse_error is True
    assert plan.diagnostics["planner_success"] is False


def test_planner_timeout_is_recorded_and_fails_closed(monkeypatch):
    client = TimeoutPlannerClient()
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.passes == []
    assert plan.backend_unavailable is True
    assert plan.diagnostics["planner_timeout"] is True


def test_pass_graph_gate_still_validates_parsed_plan(monkeypatch):
    client = ContentOnlyPlannerClient([_planner_json(passes=[{"pass_id": "p1", "subtask": "bad", "path": "BROKEN", "depends_on": [], "can_run_parallel": True}])])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])
    gate = PassGraphGate().check(plan)

    assert gate.passed is False
    assert gate.error_type == "invalid_path"


def test_llm_final_answer_composer_prefers_sdk_toolcall_structured_output(monkeypatch):
    client = ToolCallClient(
        "submit_final_answer",
        {
            "final_answer": "There are 2 campaigns.",
            "used_pass_ids": ["p1"],
            "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["p1"]}],
            "caveats_included": [],
            "unanswered_subtasks": [],
        },
    )
    monkeypatch.setattr("dashagent.llm_final_answer_composer.get_llm_client", lambda: client)

    candidate = compose_llm_final_answer(card={"task": "LLM_OWNED_FINAL_ANSWER_COMPOSITION"})

    assert candidate.final_answer == "There are 2 campaigns."
    assert candidate.used_pass_ids == ["p1"]
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_final_answer"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_final_answer"
