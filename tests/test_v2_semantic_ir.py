from __future__ import annotations

import json

import pytest

from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict
from dashagent.v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from dashagent.v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from dashagent.v2_semantic_ir_planner import (
    _build_semantic_ir_prompt_context,
    _semantic_ir_source_selection_rules,
    _semantic_ir_user_prompt,
    semantic_ir_tool_schema,
)
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


class ToolNameAwareClient(ToolCallSemanticIRClient):
    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice, "parallel_tool_calls": parallel_tool_calls, **kwargs})
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        response = self.responses.pop(0)
        if isinstance(response, str):
            return {
                "ok": True,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "content": response,
                "tool_calls": [],
                "finish_reason": "stop",
            }
        expected_tool = response.get("tool_name") or (tool_choice or {}).get("function", {}).get("name") or "submit_semantic_ir_plan"
        arguments = response.get("arguments", response)
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": expected_tool,
                    "arguments": arguments,
                }
            ],
            "finish_reason": "tool_calls",
        }


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
            "examples": [{"query": "profile-enabled ExperienceEvent schemas"}],
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


def _large_schema_context() -> dict:
    tables: dict[str, dict] = {}
    for table_idx in range(28):
        columns = [
            {"name": "ID", "type": "VARCHAR"},
            {"name": "NAME", "type": "VARCHAR"},
            {"name": "STATUS", "type": "VARCHAR"},
            {"name": "CREATEDTIME", "type": "VARCHAR"},
            {"name": "UPDATEDTIME", "type": "VARCHAR"},
            {"name": f"RELATIONSHIP_SOURCE_ID_{table_idx}", "type": "VARCHAR"},
            {"name": f"RELATIONSHIP_TARGET_ID_{table_idx}", "type": "VARCHAR"},
        ]
        columns.extend({"name": f"EXTRA_COLUMN_{table_idx}_{col_idx}", "type": "VARCHAR"} for col_idx in range(24))
        tables[f"dim_large_entity_{table_idx}"] = {
            "columns": columns,
            "description": "large schema row " * 40,
        }
    return {"tables": tables}


def _large_endpoint_context() -> list[dict]:
    endpoints: list[dict] = []
    for idx in range(34):
        endpoints.append(
            {
                "id": f"large_endpoint_{idx}",
                "method": "GET",
                "path": f"/large/resource/{idx}",
                "path_params": [],
                "common_params": {f"param_{i}": f"value_{i}" for i in range(10)},
                "domains": [f"domain_{i}" for i in range(8)],
                "examples": [{"query": f"example query {idx} " * 20, "params": {"limit": 50}}],
                "use_when": "large endpoint description " * 60,
            }
        )
    return endpoints


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


def _unsupported_local_group_plan() -> dict:
    payload = _local_count_plan()
    payload["tasks"][0].update(
        {
            "task_id": "group_status",
            "operation": "LIST",
            "description": "Count campaigns grouped by status.",
            "requires_raw_sql_fallback": True,
            "raw_sql_reason": "Needs GROUP BY status, which LocalQueryIR v1 cannot represent.",
            "unsupported_features": ["GROUP_BY"],
            "local_query": {
                "table": "dim_campaign",
                "fields": ["STATUS"],
                "filters": [],
                "limit": 50,
                "count": False,
            },
        }
    )
    payload["aggregation_instruction"] = "Answer with counts grouped by status."
    return payload


def _alias_contract(*, operation: str = "STATUS", fields: list[str] | None = None) -> dict:
    return {
        "source": "LOCAL_SNAPSHOT",
        "object": "journey",
        "entity": "Birthday Message",
        "operation": operation,
        "fields": fields or ["NAME", "STATUS"],
        "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
        "scope": "local",
        "freshness": "same_run",
    }


def _semantic_alias_plan() -> dict:
    contract = _alias_contract()
    payload = _local_count_plan()
    payload["tasks"] = [
        {
            "task_id": "local_status",
            "kind": "LOCAL_QUERY",
            "operation": "STATUS",
            "source": "LOCAL_SNAPSHOT",
            "local_query": {
                "table": "dim_campaign",
                "fields": ["NAME", "STATUS"],
                "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
                "limit": 1,
                "count": False,
            },
            "api_query": None,
            "depends_on": [],
            "description": "Get local status.",
            "required": True,
            "semantic_cache_key": "local_status:Birthday Message",
            "result_contract": contract,
        },
        {
            "task_id": "local_status_again",
            "kind": "CACHE_ALIAS",
            "operation": "STATUS",
            "source": "LOCAL_SNAPSHOT",
            "local_query": None,
            "api_query": None,
            "depends_on": ["local_status"],
            "description": "Reuse the same local status result.",
            "required": True,
            "reuse_result_from": "local_status",
            "semantic_cache_key": "local_status:Birthday Message",
            "result_contract": dict(contract),
        },
    ]
    payload["aggregation_instruction"] = "Use local_status for the status and local_status_again as the same-run alias."
    return payload


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
    task_schema = tool["function"]["parameters"]["properties"]["tasks"]["items"]
    assert "CACHE_ALIAS" in task_schema["properties"]["kind"]["enum"]
    assert "reuse_result_from" in task_schema["properties"]
    assert "semantic_cache_key" in task_schema["properties"]
    assert "result_contract" in task_schema["properties"]


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


def test_semantic_ir_parses_cache_alias_contract_and_serializes_it():
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_semantic_alias_plan()))

    alias = plan.tasks[1]
    assert alias.kind == "CACHE_ALIAS"
    assert alias.reuse_result_from == "local_status"
    assert alias.semantic_cache_key == "local_status:Birthday Message"
    assert alias.result_contract.source == "LOCAL_SNAPSHOT"
    assert alias.result_contract.operation == "STATUS"
    assert alias.result_contract.fields == ["NAME", "STATUS"]

    serialized = semantic_plan_to_dict(plan)
    assert serialized["tasks"][1]["reuse_result_from"] == "local_status"
    assert serialized["tasks"][1]["local_query"] is None
    assert serialized["tasks"][1]["api_query"] is None
    assert serialized["tasks"][1]["result_contract"]["scope"] == "local"


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
    assert [row["table"] for row in schema_card] == ["dim_schema", "dim_campaign"]
    assert schema_card[0]["columns"] == ["SCHEMAID", "NAME", "STATUS"]
    assert schema_card[1]["columns"] == ["CAMPAIGNID", "NAME", "STATUS", "PUBLISHEDAT"]

    api_card = build_allowed_api_context_card(_endpoint_context())
    assert [row["endpoint_id"] for row in api_card] == ["schemas_list", "journey_list"]
    assert api_card[0]["method"] == "GET"
    assert "unsafe_write" not in json.dumps(api_card)


def test_context_cards_include_mechanical_role_and_field_hints():
    schema_card = build_allowed_local_schema_card(_schema_context())
    schema = next(row for row in schema_card if row["table"] == "dim_schema")
    campaign = next(row for row in schema_card if row["table"] == "dim_campaign")

    assert "schema" in schema["table_role_hints"]
    assert "snapshot_record_table" in schema["table_role_hints"]
    assert schema["field_hints"]["id_fields"] == ["SCHEMAID"]
    assert schema["field_hints"]["name_fields"] == ["NAME"]
    assert schema["field_hints"]["status_fields"] == ["STATUS"]
    assert "journey" in campaign["table_role_hints"]
    assert "campaign" in campaign["table_role_hints"]
    assert campaign["field_hints"]["date_fields"] == ["PUBLISHEDAT"]


def test_api_context_card_exposes_domains_common_params_and_examples_for_llm_selection():
    api_card = build_allowed_api_context_card(_endpoint_context())
    schemas = next(row for row in api_card if row["endpoint_id"] == "schemas_list")

    assert schemas["domains"] == []
    assert schemas["common_params"] == {"limit": 25}
    assert schemas["query_params"] == ["limit"]
    assert schemas["examples"] == [{"query": "profile-enabled ExperienceEvent schemas"}]


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


def test_semantic_ir_validator_accepts_valid_alias_and_rejects_invalid_alias_contract():
    validator = SemanticIRValidator(build_allowed_local_schema_card(_schema_context()), build_allowed_api_context_card(_endpoint_context()))

    valid = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(_semantic_alias_plan())))
    assert valid.passed is True
    assert valid.semantic_alias_validation_used is True
    assert valid.semantic_alias_validation_passed is True
    assert valid.semantic_alias_count == 1

    invalid = _semantic_alias_plan()
    invalid["tasks"][1]["result_contract"]["operation"] = "DATE"
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(invalid)))
    assert failed.passed is False
    assert failed.error_type == "invalid_semantic_alias"
    assert failed.task_id == "local_status_again"
    assert failed.reuse_result_from == "local_status"
    assert failed.semantic_alias_validation_used is True
    assert failed.semantic_alias_validation_passed is False


def test_semantic_ir_validator_rejects_local_count_without_count_query():
    payload = _local_count_plan()
    payload["tasks"][0] = {
        "task_id": "schema_count",
        "kind": "AGGREGATE",
        "operation": "COUNT",
        "source": "LOCAL_SNAPSHOT",
        "local_query": None,
        "api_query": None,
        "depends_on": ["schema_list"],
        "description": "Count schema records from a prior list.",
        "required": True,
    }
    payload["tasks"].insert(
        0,
        {
            "task_id": "schema_list",
            "kind": "LOCAL_QUERY",
            "operation": "LIST",
            "source": "LOCAL_SNAPSHOT",
            "local_query": {"table": "dim_schema", "fields": ["SCHEMAID", "NAME"], "filters": [], "limit": 10, "count": False},
            "api_query": None,
            "depends_on": [],
            "description": "List schema records.",
            "required": False,
        },
    )
    validator = SemanticIRValidator(build_allowed_local_schema_card(_schema_context()), build_allowed_api_context_card(_endpoint_context()))

    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload)))

    assert failed.passed is False
    assert failed.error_type == "local_count_requires_count_query"
    assert failed.task_id == "schema_count"


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


def test_semantic_ir_compiler_compiles_cache_alias_without_sql_or_api():
    compiled = compile_semantic_ir_to_plan_payload(
        parse_semantic_ir_from_json_or_line_protocol(json.dumps(_semantic_alias_plan())),
        build_allowed_local_schema_card(_schema_context()),
        build_allowed_api_context_card(_endpoint_context()),
    )

    alias = compiled["passes"][1]
    assert alias["path"] == "CACHE_ALIAS"
    assert alias["sql"] is None
    assert alias["api_request"] is None
    assert alias["reuse_result_from"] == "local_status"
    assert alias["semantic_cache_key"] == "local_status:Birthday Message"
    assert alias["result_contract"]["operation"] == "STATUS"
    assert sum(1 for item in compiled["passes"] if item.get("sql")) == 1
    assert sum(1 for item in compiled["passes"] if item.get("api_request")) == 0


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


def test_semantic_ir_planner_prompt_keeps_local_source_preference_llm_owned(monkeypatch):
    client = ToolCallSemanticIRClient([_local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    run_llm_unified_planner(
        user_prompt="What schemas do I have?",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    system_prompt = client.calls[0]["messages"][0]["content"]
    user_payload = json.loads(client.calls[0]["messages"][1]["content"])
    rules = " ".join(user_payload["rules"])

    assert "single Unified LLM Planner facade" in system_prompt
    assert "SDK toolcall Semantic IR" in system_prompt
    assert "Prefer LOCAL_QUERY" in rules
    assert "LIVE_QUERY is the wrong source" in rules
    assert "unless the prompt names an API catalog resource" in rules
    assert "schemas alone" in rules
    assert "Schema Registry" in rules
    assert "local_query.count=true" in rules
    assert "select all relevant local timestamp candidates" in rules
    assert "relationship-bearing fields" in rules
    assert "schema class" in rules
    assert "merge policy" in rules
    assert "unless the prompt explicitly asks for live/current/platform/API" in rules
    assert "sandbox" in rules
    assert "batch" in rules
    assert "segment definitions" in rules
    assert "endpoint catalog" in rules.lower()
    assert "mixed concept plus data" in rules
    assert "compare local/live" in rules
    assert "primary_name_fields" in rules
    assert "label_fields" in rules
    assert "literal INACTIVE enum" in rules
    assert "backend" not in rules.lower() or "will not choose" in system_prompt


def test_semantic_ir_prompt_context_is_compacted_without_losing_formal_shape():
    schema_card, api_card, diagnostics = _build_semantic_ir_prompt_context(
        _large_schema_context(),
        _large_endpoint_context(),
        max_total_chars=22000,
    )

    user_prompt = _semantic_ir_user_prompt(
        user_prompt='Compare local and live status for "Birthday Message".',
        allowed_schema_card=schema_card,
        allowed_api_card=api_card,
        repair_context=None,
    )
    total_chars = len(user_prompt) + len(json.dumps(semantic_ir_tool_schema(), sort_keys=True, separators=(",", ":")))

    assert total_chars <= 22000
    assert diagnostics["semantic_ir_context_truncated"] is True
    assert diagnostics["schema_card_original_char_count"] > diagnostics["schema_card_final_char_count"]
    assert diagnostics["api_card_original_char_count"] > diagnostics["api_card_final_char_count"]
    assert diagnostics["semantic_ir_planner_char_budget"] == 22000
    assert diagnostics["schema_card_row_count"] == diagnostics["schema_card_original_row_count"]
    assert diagnostics["api_card_row_count"] == diagnostics["api_card_original_row_count"]
    assert schema_card and api_card
    assert all({"table", "columns", "table_role_hints", "field_hints"} <= set(row) for row in schema_card)
    assert all({"endpoint_id", "method", "path", "path_params", "query_params"} <= set(row) for row in api_card)


def test_semantic_ir_relationship_source_rule_stays_compact_but_preserves_required_terms():
    relationship_rule = next(rule for rule in _semantic_ir_source_selection_rules() if "relationship-bearing fields" in rule)

    assert "relationship-bearing fields" in relationship_rule
    assert "schema class" in relationship_rule
    assert "merge policy" in relationship_rule
    assert len(relationship_rule) <= 180


def test_context_cards_distinguish_primary_name_and_label_fields():
    card = build_allowed_local_schema_card(
        {
            "tables": {
                "dim_campaign": {
                    "columns": [
                        {"name": "CAMPAIGNID"},
                        {"name": "NAME"},
                        {"name": "LABELSCAMPAIGN"},
                        {"name": "SEMANTICLABELS"},
                        {"name": "STATUS"},
                        {"name": "STATE"},
                    ]
                }
            }
        }
    )

    hints = card[0]["field_hints"]
    assert hints["primary_name_fields"] == ["NAME"]
    assert hints["label_fields"] == ["LABELSCAMPAIGN", "SEMANTICLABELS"]
    assert hints["entity_lookup_fields"][:2] == ["NAME", "LABELSCAMPAIGN"]


def test_missing_toolcall_gets_one_semantic_ir_retry_before_atomic_fallback(monkeypatch):
    client = ToolCallSemanticIRClient(["plain text without tool call", _direct_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context=_schema_context(), endpoint_context=_endpoint_context())

    assert plan.route == "LLM_DIRECT"
    assert plan.diagnostics["sdk_toolcall_semantic_ir_used"] is True
    assert plan.diagnostics["atomic_protocol_fallback_used"] is False
    assert plan.diagnostics["semantic_ir_repair_attempted"] is True
    assert plan.diagnostics["semantic_ir_repair_success"] is True
    assert len(client.calls) == 2
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_semantic_ir_plan"
    assert client.calls[1]["tool_choice"]["function"]["name"] == "submit_semantic_ir_plan"


def test_semantic_ir_planner_prompt_examples_mixed_inactive_journeys_as_concept_plus_local_query(monkeypatch):
    client = ToolCallSemanticIRClient([_local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    run_llm_unified_planner(
        user_prompt="Explain what inactive journey means and show inactive journeys.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    user_payload = json.loads(client.calls[0]["messages"][1]["content"])
    examples = json.dumps(user_payload.get("semantic_ir_examples"), sort_keys=True)
    rules = " ".join(user_payload["rules"])

    assert "Explain what inactive journey means and show inactive journeys" in examples
    assert "CONCEPT" in examples
    assert "LOCAL_QUERY" in examples
    assert "LIVE_QUERY" not in examples
    assert "show/list actual records" in rules
    assert "inactive journeys" in rules


def test_semantic_ir_planner_prompt_declares_llm_owned_alias_rules(monkeypatch):
    client = ToolCallSemanticIRClient([_semantic_alias_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    run_llm_unified_planner(
        user_prompt="Show the local status of Birthday Message, then use the same local status again.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    user_payload = json.loads(client.calls[0]["messages"][1]["content"])
    rules = " ".join(user_payload["rules"])
    assert "CACHE_ALIAS" in rules
    assert "LLM owns semantic equivalence" in rules
    assert "Do not alias local and live" in rules
    assert "Do not alias status and date" in rules
    assert "result_contract" in rules


def test_semantic_ir_planner_prompt_declares_ir_support_and_raw_sql_escape_hatch(monkeypatch):
    client = ToolCallSemanticIRClient([_local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    run_llm_unified_planner(
        user_prompt="Count campaigns by status.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    user_payload = json.loads(client.calls[0]["messages"][1]["content"])
    rules = " ".join(user_payload["rules"])
    assert "Prefer supported Semantic IR operations" in rules
    assert "raw SQL fallback is an escape hatch" in rules
    assert "Do not ask the backend to write SQL" in rules
    assert "LIST/COUNT/LOOKUP/STATUS/DATE" in rules


def test_unsupported_semantic_ir_repairs_to_supported_ir_before_raw_sql(monkeypatch):
    client = ToolCallSemanticIRClient([_unsupported_local_group_plan(), _local_count_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="How many schema records are in the local snapshot?",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert plan.passes[0].sql.query == 'SELECT COUNT(*) AS count FROM "dim_schema"'
    assert plan.passes[0].raw_sql_fallback_used is False
    assert plan.diagnostics["semantic_ir_support_checked"] is True
    assert plan.diagnostics["semantic_ir_support_repair_attempted"] is True
    assert plan.diagnostics["semantic_ir_support_repair_success"] is True
    assert plan.diagnostics["raw_sql_fallback_used"] is False
    assert len(client.calls) == 2
    assert "unsupported_ir" in client.calls[1]["messages"][1]["content"]


def test_unsupported_semantic_ir_uses_llm_owned_raw_sql_fallback_after_repair(monkeypatch):
    raw_sql_response = {
        "tool_name": "submit_raw_sql_fallback",
        "arguments": {
            "task_id": "group_status",
            "reason": "Use GROUP BY for status counts.",
            "sql": "SELECT STATUS, COUNT(*) AS count FROM dim_campaign GROUP BY STATUS LIMIT 10",
            "params": [],
        },
    }
    client = ToolNameAwareClient([_unsupported_local_group_plan(), _unsupported_local_group_plan(), raw_sql_response])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="Count campaigns by status.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert plan.passes[0].raw_sql_fallback_used is True
    assert plan.passes[0].raw_sql_fallback_task_id == "group_status"
    assert plan.passes[0].sql.query == "SELECT STATUS, COUNT(*) AS count FROM dim_campaign GROUP BY STATUS LIMIT 10"
    assert plan.diagnostics["semantic_ir_support_checked"] is True
    assert plan.diagnostics["semantic_ir_support_repair_attempted"] is True
    assert plan.diagnostics["semantic_ir_support_repair_success"] is False
    assert plan.diagnostics["raw_sql_fallback_considered"] is True
    assert plan.diagnostics["raw_sql_fallback_used"] is True
    assert plan.diagnostics["backend_generated_sql"] is False
    assert [call["tool_choice"]["function"]["name"] for call in client.calls] == [
        "submit_semantic_ir_plan",
        "submit_semantic_ir_plan",
        "submit_raw_sql_fallback",
    ]


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


def test_llm_unified_planner_repairs_invalid_semantic_alias_once(monkeypatch):
    broken = _semantic_alias_plan()
    broken["tasks"][1]["result_contract"]["source"] = "LIVE_API"
    client = ToolCallSemanticIRClient([broken, _semantic_alias_plan()])
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(
        user_prompt="Show the local status of Birthday Message, then use the same local status again.",
        schema_context=_schema_context(),
        endpoint_context=_endpoint_context(),
    )

    assert [item.path for item in plan.passes] == ["SQL", "CACHE_ALIAS"]
    assert plan.diagnostics["semantic_alias_validation_used"] is True
    assert plan.diagnostics["semantic_alias_validation_passed"] is True
    assert plan.diagnostics["semantic_alias_repair_attempted"] is True
    assert plan.diagnostics["semantic_alias_count"] == 1
    assert "invalid_semantic_alias" in client.calls[1]["messages"][1]["content"]


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
            "still no tool call available",
            "RECORDS=0\nLIST=0\nCOUNT=0\nSTATUS=0\nDATE=0\nLOCAL_SNAPSHOT=0\nLIVE_CURRENT=0\nSHOW_ITEMS=0\nMIXED_CONCEPT_DATA=0\nPURE_CONCEPT=1\nDIRECT_ANSWER=A schema defines data structure.",
        ]
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={"tables": []}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.diagnostics["atomic_protocol_fallback_used"] is True
    assert plan.diagnostics["sdk_toolcall_semantic_ir_used"] is False
    assert plan.diagnostics["semantic_ir_repair_attempted"] is True
    assert plan.diagnostics["semantic_ir_repair_success"] is False
    assert len(client.calls) == 3
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_semantic_ir_plan"
    assert client.calls[1]["tools"][0]["function"]["name"] == "submit_semantic_ir_plan"
    assert client.calls[2]["tools"] is None


def test_packaged_default_remains_sql_first_api_verify():
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
