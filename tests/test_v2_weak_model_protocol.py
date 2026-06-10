from __future__ import annotations

import json

from dashagent.llm_final_answer_composer import check_final_answer_syntax, parse_llm_final_answer_response
from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.v2_weak_model_protocol import (
    parse_pass_candidate_card,
    parse_direct_route_challenge,
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


def test_parse_route_card_direct_and_evidence():
    direct = parse_route_card("ROUTE=DIRECT\nDIRECT_ANSWER=A schema defines data structure.\nREASON=pure concept")
    assert direct.route == "DIRECT"
    assert direct.direct_answer == "A schema defines data structure."

    evidence = parse_route_card("ROUTE=EVIDENCE\nDIRECT_ANSWER=\nREASON=user data")
    assert evidence.route == "EVIDENCE"
    assert evidence.direct_answer is None


def test_parse_route_card_accepts_colons_bullets_numbering_and_json():
    direct = parse_route_card("- Route : direct\n- Direct_Answer: A schema defines fields.\n- reason: meta")
    assert direct.route == "DIRECT"
    assert direct.direct_answer == "A schema defines fields."

    numbered = parse_route_card("1. ROUTE: LLM_DIRECT\n2. DIRECT_ANSWER: answer\n3. REASON: concept")
    assert numbered.route == "DIRECT"

    evidence = parse_route_card('{"route":"EVIDENCE_PIPELINE","reason":"data"}')
    assert evidence.route == "EVIDENCE"


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


def test_parse_task_ledger_accepts_colons_bullets_numbering_and_json():
    ledger = parse_task_ledger_card(
        "\n".join(
            [
                "- TASK: t1 | SQL | [] | Count schema records",
                "1. TASK: t2 | AGGREGATE | [t1] | Combine answer",
                "- AGGREGATE: Answer with the count.",
            ]
        )
    )

    assert [task.task_id for task in ledger.tasks] == ["t1", "t2"]
    assert ledger.tasks[0].path == "SQL"
    assert ledger.aggregation_instruction == "Answer with the count."

    json_ledger = parse_task_ledger_card(
        json.dumps(
            {
                "tasks": [
                    {"task_id": "q1", "path": "SQL", "depends_on": [], "subtask": "Count schemas"},
                    {"task_id": "q2", "path": "AGGREGATE", "depends_on": ["q1"], "description": "Answer"},
                ],
                "aggregation_instruction": "Combine all task results.",
            }
        )
    )
    assert [task.task_id for task in json_ledger.tasks] == ["q1", "q2"]
    assert json_ledger.aggregation_instruction == "Combine all task results."


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


def test_parse_pass_candidate_accepts_colons_and_json_cards():
    sql = parse_pass_candidate_card("1. PATH: SQL\n2. SQL: SELECT COUNT(*) FROM schemas\n3. PARAMS: []")
    assert sql.path == "SQL"
    assert sql.sql == "SELECT COUNT(*) FROM schemas"

    json_sql = parse_pass_candidate_card(json.dumps({"path": "SQL", "sql": "SELECT 1", "params": []}))
    assert json_sql.path == "SQL"
    assert json_sql.sql == "SELECT 1"

    json_api = parse_pass_candidate_card(
        json.dumps({"path": "API", "api_request": {"method": "GET", "path": "/schemas", "params": {"limit": 10}}})
    )
    assert json_api.path == "API"
    assert json_api.method == "GET"
    assert json_api.api_path == "/schemas"
    assert json_api.params == {"limit": 10}


def test_direct_route_challenge_parser_accepts_yes_no_and_rejects_missing_field():
    no = parse_direct_route_challenge("NEEDS_EVIDENCE=NO\nREASON=pure concept")
    assert no.needs_evidence is False
    assert no.reason == "pure concept"

    yes = parse_direct_route_challenge("- needs_evidence: yes\n- reason: user records")
    assert yes.needs_evidence is True

    try:
        parse_direct_route_challenge("REASON=missing decision")
    except Exception as exc:
        assert "NEEDS_EVIDENCE" in str(exc)
    else:
        raise AssertionError("challenge without NEEDS_EVIDENCE should fail")


def test_run_llm_unified_planner_uses_universal_protocol_for_direct(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=DIRECT\nDIRECT_ANSWER=A schema defines the structure and meaning of data fields.\nREASON=pure concept",
            "NEEDS_EVIDENCE=NO\nREASON=pure concept",
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
    assert plan.diagnostics["direct_route_challenge_used"] is True
    assert plan.diagnostics["direct_route_challenge_needs_evidence"] is False
    assert len(client.calls) == 2
    assert "schema_context" not in client.calls[0]["messages"][1]["content"].lower()
    assert client.calls[0]["max_tokens"] == 80
    assert client.calls[1]["max_tokens"] == 40


def test_direct_route_challenge_can_force_evidence_without_backend_route_inference(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=DIRECT\nDIRECT_ANSWER=You have schemas.\nREASON=mistaken",
            "NEEDS_EVIDENCE=YES\nREASON=user-specific schema records",
            "TASK t1 | SQL | [] | List schema records\nAGGREGATE=Answer from evidence.",
            "PATH=SQL\nSQL=SELECT name FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What schemas do I have?", schema_context={"tables": [{"name": "schemas"}]}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1
    assert plan.diagnostics["direct_route_challenge_used"] is True
    assert plan.diagnostics["direct_route_challenge_needs_evidence"] is True
    assert plan.diagnostics["backend_route_inference_used"] is False


def test_malformed_direct_route_challenge_repairs_once_then_accepts(monkeypatch):
    client = LineProtocolClient(
        [
            "ROUTE=DIRECT\nDIRECT_ANSWER=A schema defines fields.\nREASON=concept",
            "maybe",
            "NEEDS_EVIDENCE=NO\nREASON=pure concept",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={"tables": []}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.diagnostics["direct_route_challenge_repair_attempted"] is True
    assert plan.diagnostics["direct_route_challenge_needs_evidence"] is False


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
    assert [call["max_tokens"] for call in client.calls] == [80, 300, 220]


def test_call_text_gracefully_retries_for_clients_without_max_token_kwargs(monkeypatch):
    class OldSignatureClient(LineProtocolClient):
        def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
            return super().generate_messages(messages, tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)

    client = OldSignatureClient(
        [
            "ROUTE=EVIDENCE\nDIRECT_ANSWER=\nREASON=data",
            "TASK t1 | SQL | [] | Count schemas\nAGGREGATE=Answer with count.",
            "PATH=SQL\nSQL=SELECT COUNT(*) FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="How many schemas?", schema_context={"tables": [{"name": "schemas"}]}, endpoint_context=[])

    assert plan.route == "EVIDENCE_PIPELINE"
    assert len(plan.passes) == 1


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


def test_candidate_repair_prompt_includes_gate_error_and_context(monkeypatch):
    client = LineProtocolClient(
        [
            "not-json",
            "PATH=SQL\nSQL=SELECT COUNT(*) FROM schemas\nPARAMS=[]",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    previous_plan = {
        "route": "EVIDENCE_PIPELINE",
        "evidence_order": "SQL_FIRST",
        "passes": [
            {
                "pass_id": "t1",
                "subtask": "Count schemas",
                "path": "SQL",
                "depends_on": [],
                "sql": {"query": "SELECT broken FROM schemas", "params": []},
                "api_request": None,
            }
        ],
    }
    plan = run_llm_unified_planner(
        user_prompt="How many schemas?",
        schema_context={"tables": [{"name": "schemas", "columns": ["id", "name"]}]},
        endpoint_context=[],
        repair_context={
            "failed_component": "sql",
            "pass_id": "t1",
            "subtask": "Count schemas",
            "previous_plan": previous_plan,
            "sql_compile_gate": {"error_message": "no such column: broken"},
        },
    )

    assert plan.passes[0].sql.query == "SELECT COUNT(*) FROM schemas"
    repair_prompt = "\n".join(call["messages"][1]["content"] for call in client.calls)
    assert "no such column: broken" in repair_prompt
    assert "Schema context" in repair_prompt
    assert "schemas" in repair_prompt


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
