from __future__ import annotations

import json
from pathlib import Path

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.v2_dbsnapshot_preflight import check_v2_dbsnapshot_preflight
from dashagent.v2_schema_grounding import bind_semantic_ir_schema_aliases, resolve_table_alias
from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol
from dashagent.v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from dashagent.v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from dashagent.v2_semantic_ir_validator import SemanticIRValidator


def _real_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    return Config.from_env(root)


def _schema_card() -> list[dict]:
    db = DuckDBDatabase(_real_config())
    try:
        return build_allowed_local_schema_card(db.get_schema_summary())
    finally:
        db.close()


def _api_card() -> list[dict]:
    return build_allowed_api_context_card([])


def _local_count_payload(table: str) -> dict:
    return {
        "route": "EVIDENCE",
        "direct_answer": None,
        "tasks": [
            {
                "task_id": "t_schema_count",
                "kind": "LOCAL_QUERY",
                "operation": "COUNT",
                "source": "LOCAL_SNAPSHOT",
                "local_query": {"table": table, "fields": [], "filters": [], "limit": None, "count": True},
                "api_query": None,
                "depends_on": [],
                "description": "Count local schema records.",
                "required": True,
            }
        ],
        "answer_contract": {
            "required_slots": [
                {
                    "slot_id": "s_count",
                    "type": "COUNT",
                    "required": True,
                    "subject": "schemas",
                    "source_scope": "LOCAL_SNAPSHOT",
                    "satisfied_by_tasks": ["t_schema_count"],
                    "required_fields": ["count"],
                    "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER",
                    "if_missing": "FAIL_REQUIRED",
                }
            ],
            "optional_slots": [],
            "answer_style": "COUNT_ONLY",
            "global_scope": "LOCAL_SNAPSHOT",
            "contract_version": "v1",
        },
        "aggregation_instruction": "Answer with the local count.",
    }


def _birthday_lookup_payload(table: str) -> dict:
    payload = _local_count_payload(table)
    payload["tasks"][0] = {
        "task_id": "t_birthday",
        "kind": "LOCAL_QUERY",
        "operation": "DATE",
        "source": "LOCAL_SNAPSHOT",
        "local_query": {
            "table": table,
            "fields": ["NAME", "LASTDEPLOYEDTIME"],
            "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
            "limit": 1,
            "count": False,
        },
        "api_query": None,
        "depends_on": [],
        "description": "Find local Birthday Message deployment date.",
        "required": True,
    }
    payload["answer_contract"]["required_slots"][0].update(
        {
            "slot_id": "s_birthday_date",
            "type": "DATE",
            "subject": "Birthday Message",
            "object": "journey",
            "relation": "published",
            "satisfied_by_tasks": ["t_birthday"],
            "required_fields": ["LASTDEPLOYEDTIME"],
            "zero_rows_semantics": "NO_MATCH",
            "if_missing": "FAIL_REQUIRED",
        }
    )
    payload["answer_contract"]["answer_style"] = "CONCISE"
    return payload


def test_v2_dbsnapshot_preflight_detects_expected_local_tables():
    result = check_v2_dbsnapshot_preflight(_real_config())

    assert result.passed is True
    assert result.parquet_count == 18
    assert result.expected_table_row_counts["dim_blueprint"] == 74
    assert result.expected_table_row_counts["dim_campaign"] == 2
    assert result.expected_table_row_counts["dim_segment"] == 13
    assert result.expected_table_row_counts["dim_collection"] == 37


def test_v2_dbsnapshot_preflight_skips_invalid_empty_schema_parquet():
    result = check_v2_dbsnapshot_preflight(_real_config())

    assert "hkg_br_property_property" in result.skipped_invalid_tables
    assert result.passed is True


def test_schema_alias_schemas_binds_to_dim_blueprint():
    assert resolve_table_alias("schemas", {"dim_blueprint", "dim_campaign"}) == "dim_blueprint"
    assert resolve_table_alias("schema records", {"dim_blueprint", "dim_campaign"}) == "dim_blueprint"
    assert resolve_table_alias("XDM schemas", {"dim_blueprint", "dim_campaign"}) == "dim_blueprint"


def test_schema_alias_journey_campaign_binds_to_dim_campaign():
    assert resolve_table_alias("journey", {"dim_blueprint", "dim_campaign"}) == "dim_campaign"
    assert resolve_table_alias("campaign activities", {"dim_blueprint", "dim_campaign"}) == "dim_campaign"


def test_unknown_physical_table_is_rejected_with_clear_error():
    schema_card = _schema_card()
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_local_count_payload("not_a_snapshot_table")))
    bind_semantic_ir_schema_aliases(plan, schema_card)

    result = SemanticIRValidator(schema_card, _api_card()).validate(plan)

    assert result.passed is False
    assert result.error_type == "unknown_table"
    assert result.bad_table == "not_a_snapshot_table"


def test_local_schema_count_alias_compiles_to_dim_blueprint_and_returns_74():
    config = _real_config()
    schema_card = _schema_card()
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_local_count_payload("schemas")))

    binding = bind_semantic_ir_schema_aliases(plan, schema_card)
    validation = SemanticIRValidator(schema_card, _api_card()).validate(plan)
    compiled = compile_semantic_ir_to_plan_payload(plan, schema_card, _api_card())
    db = DuckDBDatabase(config)
    try:
        result = db.execute_sql(compiled["passes"][0]["sql"]["query"], params=compiled["passes"][0]["sql"]["params"], allow_full_result=True)
    finally:
        db.close()

    assert binding.bindings[0]["from_table"] == "schemas"
    assert binding.bindings[0]["to_table"] == "dim_blueprint"
    assert validation.passed is True
    assert compiled["passes"][0]["sql"]["query"] == 'SELECT COUNT(*) AS count FROM "dim_blueprint"'
    assert result["rows"][0]["count"] == 74


def test_birthday_message_lookup_alias_targets_dim_campaign_name():
    schema_card = _schema_card()
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_birthday_lookup_payload("journey")))

    bind_semantic_ir_schema_aliases(plan, schema_card)
    validation = SemanticIRValidator(schema_card, _api_card()).validate(plan)
    compiled = compile_semantic_ir_to_plan_payload(plan, schema_card, _api_card())

    assert validation.passed is True
    assert compiled["passes"][0]["sql"]["query"] == 'SELECT "NAME", "LASTDEPLOYEDTIME" FROM "dim_campaign" WHERE "NAME" = ? LIMIT 1'
    assert compiled["passes"][0]["sql"]["params"] == ["Birthday Message"]


def test_evidence_local_cannot_be_satisfied_by_direct_only_plan():
    payload = _local_count_payload("schemas")
    payload["route"] = "DIRECT"
    payload["direct_answer"] = "You have schemas."
    payload["tasks"] = [
        {
            "task_id": "t_direct",
            "kind": "CONCEPT",
            "operation": "EXPLAIN",
            "source": "NONE",
            "local_query": None,
            "api_query": None,
            "depends_on": [],
            "description": "Answer directly.",
            "required": True,
        }
    ]
    payload["answer_contract"]["required_slots"][0]["satisfied_by_tasks"] = ["t_direct"]
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload))

    result = SemanticIRValidator(_schema_card(), _api_card()).validate(plan)

    assert result.passed is False
    assert result.error_type == "direct_route_with_evidence_contract"


def test_evidence_local_cannot_be_satisfied_by_api_only_plan():
    payload = _local_count_payload("schemas")
    payload["tasks"] = [
        {
            "task_id": "t_api_only",
            "kind": "LIVE_QUERY",
            "operation": "COUNT",
            "source": "LIVE_API",
            "local_query": None,
            "api_query": {
                "endpoint_id": "schemas",
                "method": "GET",
                "path_params": {},
                "query_params": {},
            },
            "depends_on": [],
            "description": "Count live schemas.",
            "required": True,
        }
    ]
    payload["answer_contract"]["required_slots"][0]["satisfied_by_tasks"] = ["t_api_only"]
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload))

    result = SemanticIRValidator(_schema_card(), [{"endpoint_id": "schemas"}]).validate(plan)

    assert result.passed is False
    assert result.error_type == "slot_scope_task_mismatch"
