from __future__ import annotations

import json

from dashagent.llm_final_answer_composer import compose_llm_final_answer
from dashagent.llm_unified_planner import (
    _compact_api_endpoint_context,
    _planner_payload,
    planner_provider_capabilities,
    run_llm_unified_planner,
)
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


def test_planner_json_fallback_extracts_surrounding_text(monkeypatch):
    client = ContentOnlyPlannerClient(["Here is the plan:\n" + _planner_json() + "\nDone."])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1


def test_planner_json_fallback_cleans_trailing_commas(monkeypatch):
    client = ContentOnlyPlannerClient(
        [
            """
            {
              "route": "EVIDENCE_PIPELINE",
              "evidence_order": "SQL_FIRST",
              "direct_answer": null,
              "passes": [
                {
                  "pass_id": "pass_1",
                  "subtask": "Count schema records.",
                  "path": "SQL",
                  "can_run_parallel": true,
                  "depends_on": [],
                  "sql": {"query": "SELECT COUNT(*) AS count FROM schemas", "params": [],},
                  "api_request": null,
                  "expected_result": "schema count",
                },
              ],
              "aggregation_instruction": "Answer with the count.",
              "reason": "data request",
            }
            """
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas do I have?", schema_context={}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1
    assert plan.diagnostics["planner_repair_attempted"] is False


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


def test_planner_prompt_contains_compact_examples_for_concept_data_local_and_mixed() -> None:
    payload = _planner_payload(
        user_prompt="unit",
        schema_context={},
        endpoint_context=[],
        repair_context=None,
        compact_for_weak_model=True,
    )
    examples = payload["examples"]
    prompts = [row["user_prompt"] for row in examples]

    assert "What is a schema?" in prompts
    assert "What schemas do I have?" in prompts
    assert "How many schema records are in the local snapshot?" in prompts
    assert "Explain what inactive journey means and show inactive journeys." in prompts
    assert "Compare local and live status of Birthday Message if both are available." in prompts
    assert len(examples) >= 5


def test_planner_examples_do_not_contain_angle_bracket_placeholders() -> None:
    payload = _planner_payload(
        user_prompt="unit",
        schema_context={"tables": [{"name": "dim_campaign", "columns": ["name", "status", "campaign_id"]}]},
        endpoint_context=[],
        repair_context=None,
        compact_for_weak_model=True,
    )
    text = json.dumps(payload["examples"], sort_keys=True)

    assert "<schema_table>" not in text
    assert "<journey_table>" not in text
    assert "<" not in text
    assert "dim_campaign" in text


def test_planner_prompt_requires_evidence_pipeline_to_include_passes() -> None:
    payload = _planner_payload(
        user_prompt="unit",
        schema_context={},
        endpoint_context=[],
        repair_context=None,
        compact_for_weak_model=True,
    )
    constraints = "\n".join(payload["constraints"])

    assert "If route is EVIDENCE_PIPELINE, include at least one pass" in constraints
    assert "For mixed prompts, include a concept/direct pass and a SQL/API evidence pass" in constraints
    assert "Never output angle-bracket placeholders" in constraints


def test_weak_model_payload_uses_compact_api_endpoint_context() -> None:
    payload = _planner_payload(
        user_prompt="Compare local and live status of Birthday Message if both are available.",
        schema_context={},
        endpoint_context=[
            {
                "id": "journey_list",
                "method": "GET",
                "path": "/ajo/journey",
                "use_when": "List journeys and statuses.",
                "common_params": {"limit": 50, "start": 0},
                "path_params": [],
                "domains": ["JOURNEY_CAMPAIGN"],
                "extra": {"large": "ignored"},
            }
        ],
        repair_context=None,
        compact_for_weak_model=True,
    )

    endpoints = payload["allowed_api_endpoints"]
    assert endpoints == [
        {
            "method": "GET",
            "path": "/ajo/journey",
            "params": ["limit", "start"],
            "description": "List journeys and statuses.",
            "safe_get": True,
        }
    ]
    constraints = "\n".join(payload["constraints"])
    assert "For live/current/platform/compare local-vs-live prompts, include an API pass" in constraints


def test_compact_api_endpoint_context_limits_and_preserves_shape() -> None:
    endpoints = [
        {"method": "POST", "path": "/unsafe", "common_params": {"x": 1}, "use_when": "unsafe"},
        {"method": "GET", "path": "/safe", "common_params": {"limit": 25}, "use_when": "safe endpoint"},
        {"method": "GET", "path": "/safe2", "path_params": ["id"], "use_when": "safe endpoint two"},
    ]

    compact = _compact_api_endpoint_context(endpoints, max_endpoints=1)

    assert compact == [
        {
            "method": "GET",
            "path": "/safe",
            "params": ["limit"],
            "description": "safe endpoint",
            "safe_get": True,
        }
    ]


def test_pioneer_capability_metadata_is_not_mistral_specific() -> None:
    mistral = planner_provider_capabilities("pioneer_chat", "mistralai/Mistral-Nemo-Instruct-2407")
    qwen = planner_provider_capabilities("pioneer_chat", "Qwen/Qwen3-4B-Instruct-2507")

    assert mistral == qwen
    assert mistral.supports_tool_calls is False
    assert mistral.supports_json_content_fallback is True


def test_final_answer_composer_uses_json_content_when_toolcalls_unavailable(monkeypatch):
    client = ContentOnlyPlannerClient(
        [
            json.dumps(
                {
                    "final_answer": "There are 3 schema records in the local snapshot.",
                    "used_pass_ids": ["pass_1"],
                    "claimed_facts": [{"claim": "There are 3 schema records.", "supporting_pass_ids": ["pass_1"]}],
                    "caveats_included": [],
                }
            )
        ],
        provider="pioneer_chat",
        model="mistral",
    )
    monkeypatch.setattr("dashagent.llm_final_answer_composer.get_llm_client", lambda: client)

    candidate = compose_llm_final_answer(card={"task": "LLM_OWNED_FINAL_ANSWER_COMPOSITION"})

    assert candidate.final_answer == "There are 3 schema records in the local snapshot."
    assert candidate.used_pass_ids == ["pass_1"]
    assert client.calls[0]["tools"] is None


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
