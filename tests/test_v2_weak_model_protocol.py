from __future__ import annotations

import json

from dashagent.llm_final_answer_composer import check_final_answer_syntax, parse_llm_final_answer_response
from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.v2_weak_model_protocol import (
    parse_pass_candidate_card,
    parse_route_card,
    parse_task_ledger_card,
)


class LineProtocolClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "pioneer_chat"

    def model_name(self) -> str:
        return "weak-line-model"

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": self.responses.pop(0),
            "tool_calls": [],
        }


def test_parse_route_card_direct_and_evidence():
    direct = parse_route_card("ROUTE=DIRECT\nDIRECT_ANSWER=A schema defines data structure.\nREASON=pure concept")
    assert direct.route == "DIRECT"
    assert direct.direct_answer == "A schema defines data structure."

    evidence = parse_route_card("ROUTE=EVIDENCE\nDIRECT_ANSWER=\nREASON=user data")
    assert evidence.route == "EVIDENCE"
    assert evidence.direct_answer is None


def test_parse_task_ledger_mixed_prompt_with_direct_and_sql_tasks():
    ledger = parse_task_ledger_card(
        "\n".join(
            [
                "TASK t1 | DIRECT | [] | Explain inactive journey concept",
                "TASK t2 | SQL | [] | Find inactive journeys in local snapshot",
                "TASK t3 | AGGREGATE | [t1,t2] | Combine concept and data",
                "AGGREGATE=Combine all task results.",
            ]
        )
    )

    assert [task.task_id for task in ledger.tasks] == ["t1", "t2", "t3"]
    assert [task.path for task in ledger.tasks] == ["DIRECT", "SQL", "AGGREGATE"]
    assert ledger.tasks[2].depends_on == ["t1", "t2"]
    assert ledger.shape_error is None


def test_task_ledger_shape_gate_rejects_aggregate_without_dependencies():
    ledger = parse_task_ledger_card("TASK t1 | AGGREGATE | [] | Combine\nAGGREGATE=Combine.")

    assert ledger.shape_error == "aggregation_without_dependencies"


def test_parse_pass_candidate_sql_and_api_cards():
    sql = parse_pass_candidate_card("PATH=SQL\nSQL=SELECT COUNT(*) AS count FROM schemas\nPARAMS=[]")
    assert sql.path == "SQL"
    assert sql.sql == "SELECT COUNT(*) AS count FROM schemas"
    assert sql.params == []

    api = parse_pass_candidate_card('PATH=API\nMETHOD=GET\nAPI_PATH=/data/core/schemas\nPARAMS={"name":"Birthday Message"}')
    assert api.path == "API"
    assert api.method == "GET"
    assert api.api_path == "/data/core/schemas"
    assert api.params == {"name": "Birthday Message"}


def test_run_llm_unified_planner_uses_universal_protocol_for_direct(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=DIRECT\nDIRECT_ANSWER=A schema defines the structure and meaning of data fields.\nREASON=pure concept",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={"tables": []}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.evidence_order == "NO_EVIDENCE"
    assert plan.direct_answer == "A schema defines the structure and meaning of data fields."
    assert plan.passes == []
    assert plan.diagnostics["weak_protocol_route_card_used"] is True
    assert plan.diagnostics["weak_protocol_task_ledger_used"] is False
    assert len(client.calls) == 1
    assert "schema_context" not in client.calls[0]["messages"][1]["content"].lower()


def test_run_llm_unified_planner_uses_task_ledger_then_single_sql_candidate(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=EVIDENCE\nDIRECT_ANSWER=\nREASON=local count",
            "TASK t1 | SQL | [] | Count schema records in local snapshot\nAGGREGATE=Answer with the count.",
            "PATH=SQL\nSQL=SELECT COUNT(*) AS count FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="How many schema records are in the local snapshot?",
        schema_context={"tables": [{"name": "schemas", "columns": ["id", "name"]}]},
        endpoint_context=[],
    )

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.evidence_order == "SQL_FIRST"
    assert len(plan.passes) == 1
    assert plan.passes[0].pass_id == "t1"
    assert plan.passes[0].path == "SQL"
    assert plan.passes[0].sql.query == "SELECT COUNT(*) AS count FROM schemas"
    assert plan.diagnostics["weak_protocol_task_ledger_used"] is True
    assert plan.diagnostics["pass_candidate_cards"] == 1
    assert len(client.calls) == 3


def test_malformed_route_card_repairs_once_then_fails_closed_to_evidence(monkeypatch):
    client = LineProtocolClient(
        [
            "not a route card",
            "still malformed",
            "TASK t1 | SQL | [] | Count schemas\nAGGREGATE=Answer with count.",
            "PATH=SQL\nSQL=SELECT COUNT(*) AS count FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What schemas do I have?", schema_context={"tables": [{"name": "schemas"}]}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.diagnostics["route_card_repair_attempted"] is True
    assert plan.diagnostics["route_card_success"] is False
    assert plan.diagnostics["backend_route_inference_used"] is False
    assert plan.diagnostics["weak_protocol_task_ledger_used"] is True


def test_final_answer_parser_accepts_plain_text_for_weak_protocol():
    candidate = parse_llm_final_answer_response("There are 2 schema records in the local snapshot.", allow_plain_text=True)

    assert candidate.parse_error is False
    assert candidate.final_answer == "There are 2 schema records in the local snapshot."
    assert check_final_answer_syntax(candidate).passed is True


def test_protocol_prompts_do_not_contain_gold_or_query_ids(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=EVIDENCE\nDIRECT_ANSWER=\nREASON=data",
            "TASK t1 | SQL | [] | Count schemas\nAGGREGATE=Answer with count.",
            "PATH=SQL\nSQL=SELECT COUNT(*) AS count FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    run_llm_unified_planner(user_prompt="How many schemas?", schema_context={"tables": [{"name": "schemas"}]}, endpoint_context=[])
    serialized = json.dumps(client.calls, sort_keys=True).lower()

    assert "gold_answer" not in serialized
    assert "expected_trace" not in serialized
    assert "oracle" not in serialized
    assert "query_id" not in serialized
