from __future__ import annotations

import json

from dashagent.v2_answer_contract import parse_answer_contract
from dashagent.v2_schema_binding import parse_schema_binding_plan, schema_binding_plan_to_dict
from dashagent.v2_schema_binding_planner import (
    _schema_binding_user_prompt,
    schema_binding_tool_schema,
)
from dashagent.v2_schema_binding_validator import SchemaBindingValidator
from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol
from dashagent.v2_semantic_ir_context import build_allowed_local_schema_card


def _schema_card() -> list[dict]:
    return build_allowed_local_schema_card(
        {
            "tables": {
                "dim_blueprint": {
                    "columns": [
                        {"name": "BLUEPRINTID"},
                        {"name": "NAME"},
                        {"name": "CREATEDAT"},
                        {"name": "UPDATEDAT"},
                    ]
                },
                "dim_campaign": {
                    "columns": [
                        {"name": "CAMPAIGNID"},
                        {"name": "NAME"},
                        {"name": "STATUS"},
                        {"name": "LASTDEPLOYEDTIME"},
                    ]
                },
                "hkg_br_segment_campaign": {
                    "columns": [
                        {"name": "SEGMENTID"},
                        {"name": "CAMPAIGNID"},
                    ]
                },
            }
        }
    )


def _contract() -> dict:
    return {
        "required_slots": [
            {
                "slot_id": "s_schema",
                "type": "COUNT",
                "required": True,
                "subject": "schema records",
                "object": None,
                "relation": None,
                "source_scope": "LOCAL_SNAPSHOT",
                "satisfied_by_tasks": ["t_schema_count"],
                "required_fields": ["count"],
                "acceptable_fallback_fields": [],
                "expected_status_filter": None,
                "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER",
                "if_missing": "FAIL_REQUIRED",
                "must_not_assert_positive_if_zero_rows": False,
                "notes": None,
            }
        ],
        "optional_slots": [],
        "answer_style": "COUNT_ONLY",
        "global_scope": "LOCAL_SNAPSHOT",
        "contract_version": "v1",
    }


def _plan_payload() -> dict:
    return {
        "route": "EVIDENCE",
        "direct_answer": None,
        "tasks": [
            {
                "task_id": "t_schema_count",
                "kind": "LOCAL_QUERY",
                "operation": "COUNT",
                "source": "LOCAL_SNAPSHOT",
                "binding_id": "b_schema",
                "local_query": {
                    "binding_id": "b_schema",
                    "table": "dim_blueprint",
                    "fields": [],
                    "filters": [],
                    "limit": None,
                    "count": True,
                },
                "api_query": None,
                "depends_on": [],
                "description": "Count schema records.",
                "required": True,
            }
        ],
        "answer_contract": _contract(),
        "aggregation_instruction": "Answer with the count.",
    }


def _binding_payload(**overrides) -> dict:
    binding = {
        "binding_id": "b_schema",
        "semantic_object": "schema records",
        "object_type": "schema",
        "source_scope": "LOCAL_SNAPSHOT",
        "table": "dim_blueprint",
        "primary_id_fields": ["BLUEPRINTID"],
        "name_fields": ["NAME"],
        "status_fields": [],
        "date_fields": ["CREATEDAT", "UPDATEDAT"],
        "relation_tables": [],
        "required_for_slots": ["s_schema"],
        "confidence_note": None,
    }
    binding.update(overrides)
    return {"binding_version": "v1", "bindings": [binding]}


def test_schema_binding_plan_parses_valid_binding_and_serializes():
    plan = parse_schema_binding_plan(_binding_payload())

    assert plan.binding_version == "v1"
    assert plan.bindings[0].binding_id == "b_schema"
    assert plan.bindings[0].table == "dim_blueprint"
    assert schema_binding_plan_to_dict(plan)["bindings"][0]["primary_id_fields"] == ["BLUEPRINTID"]


def test_schema_binding_validator_rejects_unknown_table_field_relation_and_slot_without_inference():
    semantic_plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_payload()))
    validator = SchemaBindingValidator(_schema_card(), parse_answer_contract(_contract()))

    assert validator.validate(parse_schema_binding_plan(_binding_payload()), semantic_plan=semantic_plan).passed is True

    bad_table = parse_schema_binding_plan(_binding_payload(table="schemas"))
    failed = validator.validate(bad_table, semantic_plan=semantic_plan)
    assert failed.passed is False
    assert failed.error_type == "unknown_table"
    assert failed.bad_value == "schemas"
    assert "dim_blueprint" in failed.allowed_tables
    assert bad_table.bindings[0].table == "schemas"

    bad_field = parse_schema_binding_plan(_binding_payload(name_fields=["DISPLAY_NAME"]))
    failed = validator.validate(bad_field, semantic_plan=semantic_plan)
    assert failed.passed is False
    assert failed.error_type == "unknown_field"
    assert failed.binding_id == "b_schema"
    assert "NAME" in failed.allowed_fields_for_table

    bad_relation = parse_schema_binding_plan(_binding_payload(relation_tables=["missing_bridge"]))
    failed = validator.validate(bad_relation, semantic_plan=semantic_plan)
    assert failed.error_type == "invalid_relation_table"

    bad_slot = parse_schema_binding_plan(_binding_payload(required_for_slots=["missing_slot"]))
    failed = validator.validate(bad_slot, semantic_plan=semantic_plan)
    assert failed.error_type == "invalid_slot_reference"


def test_schema_binding_validator_rejects_scope_mismatch_and_local_query_conflict():
    payload = _contract()
    payload["required_slots"][0]["source_scope"] = "LIVE_API"
    semantic_plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_payload()))

    failed = SchemaBindingValidator(_schema_card(), parse_answer_contract(payload)).validate(
        parse_schema_binding_plan(_binding_payload(source_scope="LOCAL_SNAPSHOT")),
        semantic_plan=semantic_plan,
    )

    assert failed.passed is False
    assert failed.error_type == "scope_mismatch"

    conflict_payload = _plan_payload()
    conflict_payload["tasks"][0]["local_query"]["table"] = "dim_campaign"
    conflict_plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(conflict_payload))
    failed = SchemaBindingValidator(_schema_card(), parse_answer_contract(_contract())).validate(
        parse_schema_binding_plan(_binding_payload(table="dim_blueprint")),
        semantic_plan=conflict_plan,
    )

    assert failed.passed is False
    assert failed.error_type == "binding_table_conflict"
    assert conflict_plan.tasks[0].local_query.table == "dim_campaign"


def test_schema_binding_tool_schema_and_prompt_preserve_llm_ownership():
    tool = schema_binding_tool_schema()
    assert tool["function"]["name"] == "submit_schema_binding_plan"
    assert "bindings" in tool["function"]["parameters"]["properties"]

    prompt = _schema_binding_user_prompt(
        user_prompt="How many schema records are in the local snapshot?",
        semantic_plan=parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_payload())),
        answer_contract=parse_answer_contract(_contract()),
        allowed_schema_card=_schema_card(),
        validation_error=None,
    )

    assert "Bind each semantic object" in prompt
    assert "Do not write SQL" in prompt
    assert "backend will not infer" in prompt
    assert "exact table and field IDs" in prompt
    assert "query_id" not in prompt.lower()
