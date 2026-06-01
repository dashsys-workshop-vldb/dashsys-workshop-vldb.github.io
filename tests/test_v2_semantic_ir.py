from __future__ import annotations

import json

import pytest

from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict
from dashagent.v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from dashagent.v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from dashagent.v2_semantic_ir_planner import semantic_ir_tool_schema
from dashagent.v2_semantic_ir_validator import SemanticIRValidator


class ToolCallSemanticIRClient:
    def __init__(self, responses: list[dict | str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return "hermes-test-model"

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice, "parallel_tool_calls": parallel_tool_calls, **kwargs})
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        payload = self.responses.pop(0)
        if isinstance(payload, str):
            return {
                "ok": True,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "content": payload,
                "tool_calls": [],
                "finish_reason": "stop",
            }
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "submit_semantic_ir_plan",
                    "arguments": payload,
                }
            ],
            "finish_reason": "tool_calls",
        }


class NoToolCallClient(ToolCallSemanticIRClient):
    def provider_name(self) -> str:
        return "openai"


def _schema_context() -> dict:
    return {
        "tables": {
            "dim_schema": {
                "columns": [
                    {"name": "SCHEMAID", "type": "VARCHAR"},
                    {"name": "NAME", "type": "VARCHAR"},
                    {"name": "STATUS", "type": "VARCHAR"},
                ]
            },
            "dim_campaign": {
                "columns": [
                    {"name": "CAMPAIGNID", "type": "VARCHAR"},
                    {"name": "NAME", "type": "VARCHAR"},
                    {"name": "STATUS", "type": "VARCHAR"},
                    {"name": "PUBLISHEDAT", "type": "VARCHAR"},
                ]
            },
        }
    }


def _endpoint_context() -> list[dict]:
    return [
        {
            "id": "schemas_list",
            "method": "GET",
            "path": "/data/foundation/schemaregistry/tenant/schemas",
            "path_params": [],
            "common_params": {"limit": 25},
            "use_when": "List schemas.",
        },
        {
            "id": "journey_list",
            "method": "GET",
            "path": "/ajo/journey",
            "path_params": [],
            "common_params": {"limit": 50},
            "use_when": "List journeys and statuses.",
        },
        {
            "id": "unsafe_write",
            "method": "POST",
            "path": "/unsafe",
            "path_params": [],
        },
    ]


def _direct_plan() -> dict:
    return {
        "route": "DIRECT",
        "direct_answer": "A schema defines the structure and meaning of data fields.",
        "tasks": [],
        "aggregation_instruction": "Return the direct answer.",
    }


def _local_count_plan() -> dict:
    return {
        "route": "EVIDENCE",
        "direct_answer": None,
        "tasks": [
            {
                "task_id": "t1",
                "kind": "LOCAL_QUERY",
                "operation": "COUNT",
                "source": "LOCAL_SNAPSHOT",
                "local_query": {"table": "dim_schema", "fields": [], "filters": [], "limit": None, "count": True},
                "api_query": None,
                "depends_on": [],
                "description": "Count schema records.",
                "required": True,
            }
        ],
        "aggregation_instruction": "Answer with the count from t1.",
    }


def _live_plan() -> dict:
    payload = _local_count_plan()
    payload["tasks"][0].update(
        {
            "kind": "LIVE_QUERY",
            "operation": "LIST",
            "source": "LIVE_API",
            "local_query": None,
            "api_query": {"endpoint_id": "schemas_list", "method": "GET", "path_params": {}, "query_params": {"limit": 10}},
        }
    )
    return payload


def _local_and_live_plan() -> dict:
    payload = _local_count_plan()
    payload["tasks"][0].update(
        {
            "kind": "LOCAL_AND_LIVE",
            "operation": "COMPARE",
            "source": "BOTH",
            "local_query": {
                "table": "dim_campaign",
                "fields": ["NAME", "STATUS"],
                "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
                "limit": 1,
                "count": False,
            },
            "api_query": {"endpoint_id": "journey_list", "method": "GET", "path_params": {}, "query_params": {"limit": 50}},
        }
    )
    return payload


def test_tool_schema_declares_submit_semantic_ir_plan():
    tool = semantic_ir_tool_schema()
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "submit_semantic_ir_plan"
    assert "tasks" in tool["function"]["parameters"]["properties"]


def test_semantic_ir_parses_direct_and_local_live_shapes():
    direct = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_direct_plan()))
    assert direct.route == "DIRECT"
    assert direct.tasks == []

    local = parse_semantic_ir_from_json_or_line_protocol("```json\n" + json.dumps(_local_count_plan()) + "\n```")
    assert local.tasks[0].kind == "LOCAL_QUERY"
    assert local.tasks[0].local_query.table == "dim_schema"
    assert semantic_plan_to_dict(local)["tasks"][0]["operation"] == "COUNT"

    live = parse_semantic_ir_from_json_or_line_protocol("The plan is:\n" + json.dumps(_live_plan()))
    assert live.tasks[0].api_query.endpoint_id == "schemas_list"


def test_semantic_ir_rejects_invalid_enum_and_does_not_fill_missing_table():
    payload = _local_count_plan()
    payload["tasks"][0]["operation"] = "SUMMARIZE"
    with pytest.raises(ValueError, match="operation"):
        parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload))

    missing = _local_count_plan()
    missing["tasks"][0]["local_query"].pop("table")
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(missing))
    assert plan.tasks[0].local_query.table == ""


def test_context_cards_are_mechanical_and_safe_get_only():
    schema_card = build_allowed_local_schema_card(_schema_context())
    assert schema_card == [
        {"table": "dim_schema", "columns": ["SCHEMAID", "NAME", "STATUS"]},
        {"table": "dim_campaign", "columns": ["CAMPAIGNID", "NAME", "STATUS", "PUBLISHEDAT"]},
    ]

    api_card = build_allowed_api_context_card(_endpoint_context())
    assert [row["endpoint_id"] for row in api_card] == ["schemas_list", "journey_list"]
    assert api_card[0]["method"] == "GET"
    assert "unsafe_write" not in json.dumps(api_card)


def test_semantic_ir_validator_checks_existence_without_correction():
    validator = SemanticIRValidator(
        allowed_schema_card=build_allowed_local_schema_card(_schema_context()),
        allowed_api_card=build_allowed_api_context_card(_endpoint_context()),
    )
    valid = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(_local_count_plan())))
    assert valid.passed is True

    bad_table = _local_count_plan()
    bad_table["tasks"][0]["local_query"]["table"] = "schemas"
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(bad_table)))
    assert failed.passed is False
    assert failed.error_type == "unknown_table"
    assert bad_table["tasks"][0]["local_query"]["table"] == "schemas"

    bad_field = _local_count_plan()
    bad_field["tasks"][0]["local_query"]["fields"] = ["NOT_A_COLUMN"]
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(bad_field)))
    assert failed.error_type == "unknown_field"

    bad_endpoint = _live_plan()
    bad_endpoint["tasks"][0]["api_query"]["endpoint_id"] = "missing_endpoint"
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(bad_endpoint)))
    assert failed.error_type == "unknown_endpoint"


def test_semantic_ir_validator_checks_cycles_and_dependencies():
    payload = _local_count_plan()
    payload["tasks"].append(
        {
            "task_id": "t2",
            "kind": "AGGREGATE",
            "operation": "COMPARE",
            "source": "NONE",
            "local_query": None,
            "api_query": None,
            "depends_on": ["missing"],
            "description": "Aggregate.",
            "required": True,
        }
    )
    validator = SemanticIRValidator(build_allowed_local_schema_card(_schema_context()), build_allowed_api_context_card(_endpoint_context()))
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload)))
    assert failed.error_type == "unknown_dependency"

    payload["tasks"][1]["depends_on"] = ["t1"]
    payload["tasks"][0]["depends_on"] = ["t2"]
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload)))
    assert failed.error_type == "dependency_cycle"


def test_semantic_ir_compiler_mechanically_compiles_sql_and_api():
    schema_card = build_allowed_local_schema_card(_schema_context())
    api_card = build_allowed_api_context_card(_endpoint_context())

    payload = _local_count_plan()
    payload["tasks"][0]["local_query"]["filters"] = [{"field": "NAME", "op": "contains", "value": "schema"}]
    compiled = compile_semantic_ir_to_plan_payload(parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload)), schema_card, api_card)
    assert compiled["passes"][0]["sql"] == {
        "query": 'SELECT COUNT(*) AS count FROM "dim_schema" WHERE LOWER("NAME") LIKE LOWER(?)',
        "params": ["%schema%"],
    }

    list_payload = _local_count_plan()
    list_payload["tasks"][0]["operation"] = "LIST"
    list_payload["tasks"][0]["local_query"] = {
        "table": "dim_campaign",
        "fields": ["NAME", "STATUS"],
        "filters": [{"field": "STATUS", "op": "in", "value": ["inactive", "draft"]}],
        "limit": 10,
        "count": False,
    }
    compiled = compile_semantic_ir_to_plan_payload(parse_semantic_ir_from_json_or_line_protocol(json.dumps(list_payload)), schema_card, api_card)
    assert compiled["passes"][0]["sql"]["query"] == 'SELECT "NAME", "STATUS" FROM "dim_campaign" WHERE "STATUS" IN (?, ?) LIMIT 10'
    assert compiled["passes"][0]["sql"]["params"] == ["inactive", "draft"]

    compiled = compile_semantic_ir_to_plan_payload(parse_semantic_ir_from_json_or_line_protocol(json.dumps(_live_plan())), schema_card, api_card)
    assert compiled["passes"][0]["api_request"] == {
        "method": "GET",
        "path": "/data/foundation/schemaregistry/tenant/schemas",
        "params": {"limit": 10},
    }


def test_local_and_live_compiles_both_without_backend_path_choice():
    compiled = compile_semantic_ir_to_plan_payload(
        parse_semantic_ir_from_json_or_line_protocol(json.dumps(_local_and_live_plan())),
        build_allowed_local_schema_card(_schema_context()),
        build_allowed_api_context_card(_endpoint_context()),
    )
    first = compiled["passes"][0]
    assert first["path"] == "SQL_AND_API"
    assert first["sql"]["query"] == 'SELECT "NAME", "STATUS" FROM "dim_campaign" WHERE "NAME" = ? LIMIT 1'
    assert first["api_request"]["path"] == "/ajo/journey"


def test_llm_unified_planner_uses_sdk_toolcall_semantic_ir_primary_path(monkeypatch):
    client = ToolCallSemanticIRClient([_local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="How many schema records are in the local snapshot?",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert plan.route == "EVIDENCE_PIPELINE"
    assert plan.passes[0].sql.query == 'SELECT COUNT(*) AS count FROM "dim_schema"'
    assert plan.diagnostics["sdk_toolcall_semantic_ir_used"] is True
    assert plan.diagnostics["semantic_ir_toolcall_supported"] is True
    assert plan.diagnostics["semantic_ir_validation_passed"] is True
    assert plan.diagnostics["backend_semantic_planning_used"] is False
    assert plan.diagnostics["backend_formal_compilation_used"] is True
    assert plan.diagnostics["atomic_protocol_fallback_used"] is False
    assert len(client.calls) == 1
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_semantic_ir_plan"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_semantic_ir_plan"


def test_direct_toolcall_route_skips_sql_api_passes(monkeypatch):
    client = ToolCallSemanticIRClient([_direct_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context=_schema_context(), endpoint_context=_endpoint_context())

    assert plan.route == "LLM_DIRECT"
    assert plan.evidence_order == "NO_EVIDENCE"
    assert plan.direct_answer == "A schema defines the structure and meaning of data fields."
    assert plan.sql is None
    assert plan.api_request is None
    assert plan.passes == []


def test_llm_unified_planner_repairs_invalid_semantic_ir_once(monkeypatch):
    broken = _local_count_plan()
    broken["tasks"][0]["local_query"]["table"] = "schemas"
    client = ToolCallSemanticIRClient([broken, _local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="How many schema records are in the local snapshot?",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert plan.passes[0].sql.query == 'SELECT COUNT(*) AS count FROM "dim_schema"'
    assert plan.diagnostics["semantic_ir_validation_passed"] is True
    assert plan.diagnostics["semantic_ir_repair_attempted"] is True
    assert plan.diagnostics["semantic_ir_repair_success"] is True
    repair_prompt = client.calls[1]["messages"][1]["content"]
    assert "unknown_table" in repair_prompt
    assert "allowed_tables" in repair_prompt
    assert "schemas" in repair_prompt


def test_unknown_endpoint_repairs_once_and_backend_does_not_choose_replacement(monkeypatch):
    broken = _live_plan()
    broken["tasks"][0]["api_query"]["endpoint_id"] = "schema_endpoint_guess"
    client = ToolCallSemanticIRClient([broken, _live_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="List live schemas.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert plan.passes[0].api_request.path == "/data/foundation/schemaregistry/tenant/schemas"
    assert plan.diagnostics["semantic_ir_validation_error_type"] == "unknown_endpoint"
    assert plan.diagnostics["semantic_ir_repair_attempted"] is True
    assert "schema_endpoint_guess" in client.calls[1]["messages"][1]["content"]


def test_atomic_fallback_only_when_toolcall_unavailable_for_non_pioneer_tool_model(monkeypatch):
    client = NoToolCallClient(
        [
            "no tool call available",
            "RECORDS=0\nLIST=0\nCOUNT=0\nSTATUS=0\nDATE=0\nLOCAL_SNAPSHOT=0\nLIVE_CURRENT=0\nSHOW_ITEMS=0\nMIXED_CONCEPT_DATA=0\nPURE_CONCEPT=1\nDIRECT_ANSWER=A schema defines data structure.",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={"tables": []}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.diagnostics["atomic_protocol_fallback_used"] is True
    assert plan.diagnostics["sdk_toolcall_semantic_ir_used"] is False
    assert len(client.calls) == 2
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_semantic_ir_plan"
    assert client.calls[1]["tools"] is None


def test_packaged_default_remains_sql_first_api_verify():
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
