from __future__ import annotations

import json

from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.v2_atomic_weak_protocol import (
    parse_atomic_evidence_checklist,
    parse_fixed_task_slots,
    parse_slot_api_candidate,
    parse_slot_sql_candidate,
)


class AtomicClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "pioneer_chat"

    def model_name(self) -> str:
        return "weak-atomic"

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice, **kwargs})
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": self.responses.pop(0),
            "tool_calls": [],
        }


def _checklist(**bits: int | str) -> str:
    keys = [
        "RECORDS",
        "LIST",
        "COUNT",
        "STATUS",
        "DATE",
        "LOCAL_SNAPSHOT",
        "LIVE_CURRENT",
        "SHOW_ITEMS",
        "MIXED_CONCEPT_DATA",
        "PURE_CONCEPT",
        "DIRECT_ANSWER",
    ]
    values = {key: 0 for key in keys}
    values["DIRECT_ANSWER"] = ""
    values.update(bits)
    return "\n".join(f"{key}={values[key]}" for key in keys)


def test_atomic_checklist_routes_pure_concept_and_meta_direct():
    concept = parse_atomic_evidence_checklist(_checklist(PURE_CONCEPT=1, DIRECT_ANSWER="A schema defines data structure."))
    assert concept.route == "LLM_DIRECT"
    assert concept.bits["PURE_CONCEPT"] == 1
    assert concept.direct_answer == "A schema defines data structure."

    meta = parse_atomic_evidence_checklist(
        json.dumps(
            {
                "records": 0,
                "list": 0,
                "count": 0,
                "status": 0,
                "date": 0,
                "local_snapshot": 0,
                "live_current": 0,
                "show_items": 0,
                "mixed_concept_data": 0,
                "pure_concept": True,
                "direct_answer": "Here, list means enumerate.",
            }
        )
    )
    assert meta.route == "LLM_DIRECT"


def test_atomic_checklist_routes_data_prompts_to_evidence():
    for text, expected_bit in [
        (_checklist(RECORDS=1), "RECORDS"),
        (_checklist(COUNT=1), "COUNT"),
        (_checklist(DATE=1), "DATE"),
        (_checklist(MIXED_CONCEPT_DATA=1, LIST=1, SHOW_ITEMS=1), "MIXED_CONCEPT_DATA"),
    ]:
        parsed = parse_atomic_evidence_checklist(text)
        assert parsed.route == "EVIDENCE_PIPELINE"
        assert parsed.bits[expected_bit] == 1


def test_atomic_checklist_parser_accepts_colon_bullets_yes_no_chinese_and_fences():
    parsed = parse_atomic_evidence_checklist(
        """```text
        - RECORDS: no
        - LIST: 否
        - COUNT: false
        - STATUS: 0
        - DATE: 0
        - LOCAL_SNAPSHOT: 0
        - LIVE_CURRENT: 0
        - SHOW_ITEMS: 0
        - MIXED_CONCEPT_DATA: 0
        - PURE_CONCEPT: 是
        - DIRECT_ANSWER: A schema defines data.
        ```"""
    )
    assert parsed.route == "LLM_DIRECT"
    assert parsed.bits["PURE_CONCEPT"] == 1


def test_fixed_task_slots_parse_five_slots_letters_none_and_shape_gate():
    slots = parse_fixed_task_slots(
        "\n".join(
            [
                "T1_PATH=B",
                "T1_DEPS=[]",
                "T1_DESC=Count schemas",
                "T2_PATH=N",
                "T2_DEPS=[]",
                "T2_DESC=",
                "T3_PATH=E",
                "T3_DEPS=[T1]",
                "T3_DESC=Aggregate",
                "T4_PATH=NONE",
                "T4_DEPS=[]",
                "T4_DESC=",
                "T5_PATH=NONE",
                "T5_DEPS=[]",
                "T5_DESC=",
                "AGGREGATE=Answer with count.",
            ]
        )
    )
    assert [slot.task_id for slot in slots.active_slots] == ["T1", "T3"]
    assert slots.active_slots[0].path == "SQL"
    assert slots.active_slots[1].path == "AGGREGATE"
    assert slots.shape_error is None

    bad = parse_fixed_task_slots("T1_PATH=AGGREGATE\nT1_DEPS=[]\nT1_DESC=bad\nAGGREGATE=bad")
    assert bad.shape_error == "aggregation_without_dependencies"


def test_fixed_task_slots_json_mixed_prompt_direct_plus_sql():
    slots = parse_fixed_task_slots(
        json.dumps(
            {
                "T1_PATH": "DIRECT",
                "T1_DEPS": [],
                "T1_DESC": "Explain inactive journey",
                "T2_PATH": "SQL",
                "T2_DEPS": [],
                "T2_DESC": "Find inactive journeys",
                "T3_PATH": "AGGREGATE",
                "T3_DEPS": ["T1", "T2"],
                "T3_DESC": "Combine",
                "T4_PATH": "NONE",
                "T5_PATH": "NONE",
                "AGGREGATE": "Concept plus data.",
            }
        )
    )
    assert [slot.path for slot in slots.active_slots] == ["DIRECT", "SQL", "AGGREGATE"]
    assert slots.shape_error is None


def test_slot_candidate_parsers_accept_line_and_json_shapes():
    sql = parse_slot_sql_candidate("SQL_QUERY: SELECT COUNT(*) FROM schemas\nPARAMS_JSON: []")
    assert sql.sql == "SELECT COUNT(*) FROM schemas"
    assert sql.params == []

    sql_json = parse_slot_sql_candidate(json.dumps({"query": "SELECT 1", "params": []}))
    assert sql_json.sql == "SELECT 1"

    api = parse_slot_api_candidate("METHOD=GET\nAPI_PATH=/schemas\nPARAMS_JSON={\"limit\": 10}")
    assert api.method == "GET"
    assert api.api_path == "/schemas"
    assert api.params == {"limit": 10}

    api_json = parse_slot_api_candidate(json.dumps({"method": "GET", "path": "/schemas", "params": {}}))
    assert api_json.api_path == "/schemas"


def test_run_planner_uses_atomic_checklist_for_direct(monkeypatch):
    client = AtomicClient([_checklist(PURE_CONCEPT=1, DIRECT_ANSWER="A schema defines data structure.")])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={"tables": []}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.direct_answer == "A schema defines data structure."
    assert plan.diagnostics["atomic_checklist_used"] is True
    assert plan.diagnostics["checklist_route"] == "LLM_DIRECT"
    assert plan.diagnostics["backend_semantic_routing_used"] is False
    assert len(client.calls) == 1
    assert client.calls[0]["max_tokens"] == 80


def test_run_planner_repairs_malformed_checklist_once(monkeypatch):
    client = AtomicClient(["not parseable", _checklist(PURE_CONCEPT=1, DIRECT_ANSWER="A schema defines data.")])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.diagnostics["checklist_repair_attempted"] is True
    assert len(client.calls) == 2


def test_run_planner_evidence_fixed_slots_and_candidates(monkeypatch):
    client = AtomicClient(
        [
            _checklist(RECORDS=1, LIST=1),
            "\n".join(
                [
                    "T1_PATH=SQL",
                    "T1_DEPS=[]",
                    "T1_DESC=List schemas",
                    "T2_PATH=NONE",
                    "T3_PATH=NONE",
                    "T4_PATH=NONE",
                    "T5_PATH=NONE",
                    "AGGREGATE=Answer with schema records.",
                ]
            ),
            "SQL_QUERY=SELECT name FROM schemas\nPARAMS_JSON=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="What schemas do I have?",
        schema_context={"tables": [{"name": "schemas", "columns": ["name"]}]},
        endpoint_context=[],
    )

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1
    assert plan.passes[0].pass_id == "T1"
    assert plan.passes[0].path == "SQL"
    assert plan.passes[0].sql.query == "SELECT name FROM schemas"
    assert plan.diagnostics["fixed_task_slots_used"] is True
    assert plan.diagnostics["atomic_candidate_slots_used"] is True
    assert [call["max_tokens"] for call in client.calls] == [80, 300, 220]


def test_candidate_repair_prompt_contains_gate_error_and_context(monkeypatch):
    client = AtomicClient(["bad generic repair", "SQL_QUERY=SELECT COUNT(*) FROM schemas\nPARAMS_JSON=[]"])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)
    previous = {
        "route": "EVIDENCE_PIPELINE",
        "evidence_order": "SQL_FIRST",
        "passes": [
            {
                "pass_id": "T1",
                "subtask": "Count schemas",
                "path": "SQL",
                "depends_on": [],
                "sql": {"query": "SELECT broken FROM schemas", "params": []},
            }
        ],
    }

    plan = run_llm_unified_planner(
        user_prompt="How many schemas?",
        schema_context={"tables": [{"name": "schemas", "columns": ["id"]}]},
        endpoint_context=[],
        repair_context={
            "failed_component": "sql",
            "pass_id": "T1",
            "previous_plan": previous,
            "sql_compile_gate": {"error_message": "no such column: broken"},
        },
    )

    assert plan.passes[0].sql.query == "SELECT COUNT(*) FROM schemas"
    prompts = "\n".join(call["messages"][1]["content"] for call in client.calls)
    assert "no such column: broken" in prompts
    assert "Schema context" in prompts
    assert "schemas" in prompts
