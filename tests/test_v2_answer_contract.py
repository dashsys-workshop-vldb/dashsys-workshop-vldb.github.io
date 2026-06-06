from __future__ import annotations

import json

import pytest

from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from dashagent.v2_answer_contract import (
    EvidenceSlotState,
    RequiredAnswerSlot,
    V2AnswerContract,
    answer_contract_from_plan_dict,
    answer_contract_to_dict,
    evidence_slot_state_to_dict,
    parse_answer_contract,
    validate_answer_contract_shape,
)
from dashagent.v2_answer_contract_validator import AnswerContractValidator
from dashagent.v2_evidence_contract import evaluate_evidence_contract
from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict


def _count_contract() -> dict:
    return {
        "required_slots": [
            {
                "slot_id": "s_count",
                "type": "COUNT",
                "required": True,
                "subject": "schemas",
                "object": None,
                "relation": None,
                "source_scope": "LOCAL_SNAPSHOT",
                "satisfied_by_tasks": ["t1"],
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


def _date_contract() -> dict:
    payload = _count_contract()
    payload["required_slots"][0].update(
        {
            "slot_id": "s_date",
            "type": "DATE",
            "subject": "Birthday Message",
            "relation": "published_date",
            "required_fields": ["PUBLISHEDAT", "LASTDEPLOYEDTIME"],
            "acceptable_fallback_fields": ["CREATEDTIME", "UPDATEDTIME"],
            "zero_rows_semantics": "NO_MATCH",
            "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
            "must_not_assert_positive_if_zero_rows": True,
        }
    )
    payload["answer_style"] = "CAVEATED"
    return payload


def _relation_contract() -> dict:
    payload = _count_contract()
    payload["required_slots"][0].update(
        {
            "slot_id": "s_relation",
            "type": "RELATION",
            "subject": "SMS Opt-In",
            "object": "destination",
            "relation": "audience_to_destination",
            "required_fields": ["SEGMENTID", "TARGETID"],
            "acceptable_fallback_fields": [],
            "zero_rows_semantics": "NO_MATCH",
            "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
            "must_not_assert_positive_if_zero_rows": True,
        }
    )
    payload["answer_style"] = "CAVEATED"
    return payload


def _plan_with_contract(answer_contract: dict | None = None) -> dict:
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
        "answer_contract": answer_contract if answer_contract is not None else _count_contract(),
        "aggregation_instruction": "Answer from the contract slots.",
    }


def test_answer_contract_parses_valid_count_date_relation_and_serializes():
    count = parse_answer_contract(_count_contract())
    date = parse_answer_contract(_date_contract())
    relation = parse_answer_contract(_relation_contract())

    assert isinstance(count, V2AnswerContract)
    assert isinstance(count.required_slots[0], RequiredAnswerSlot)
    assert count.required_slots[0].type == "COUNT"
    assert date.required_slots[0].acceptable_fallback_fields == ["CREATEDTIME", "UPDATEDTIME"]
    assert relation.required_slots[0].type == "RELATION"
    assert answer_contract_to_dict(count)["required_slots"][0]["slot_id"] == "s_count"


def test_answer_contract_rejects_missing_slot_id_invalid_enum_and_missing_task_reference():
    missing = _count_contract()
    missing["required_slots"][0].pop("slot_id")
    with pytest.raises(ValueError, match="slot_id"):
        parse_answer_contract(missing)

    invalid = _count_contract()
    invalid["required_slots"][0]["type"] = "NUMBERISH"
    with pytest.raises(ValueError, match="type"):
        parse_answer_contract(invalid)

    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_with_contract(_count_contract())))
    bad_contract = parse_answer_contract(_count_contract())
    bad_contract.required_slots[0].satisfied_by_tasks = ["missing_task"]
    result = validate_answer_contract_shape(bad_contract, task_ids=[task.task_id for task in plan.tasks], route=plan.route)
    assert result["passed"] is False
    assert result["error_type"] == "unknown_slot_task_reference"


def test_direct_concept_plan_may_omit_evidence_answer_contract():
    plan = parse_semantic_ir_from_json_or_line_protocol(
        {
            "route": "DIRECT",
            "direct_answer": "A schema defines data structure.",
            "tasks": [],
            "answer_contract": None,
            "aggregation_instruction": "Answer directly.",
        }
    )

    assert plan.answer_contract is None
    assert semantic_plan_to_dict(plan)["answer_contract"] is None
    assert validate_answer_contract_shape(None, task_ids=[], route=plan.route)["passed"] is True


def test_answer_contract_validator_checks_task_scope_and_slot_shape():
    validator = AnswerContractValidator()
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_with_contract(_count_contract())))
    assert validator.validate(plan).passed is True

    local_slot_backed_by_api = _count_contract()
    local_slot_backed_by_api["required_slots"][0]["satisfied_by_tasks"] = ["api_task"]
    api_plan = _plan_with_contract(local_slot_backed_by_api)
    api_plan["tasks"] = [
        {
            "task_id": "api_task",
            "kind": "LIVE_QUERY",
            "operation": "COUNT",
            "source": "LIVE_API",
            "local_query": None,
            "api_query": {"endpoint_id": "schemas_list", "method": "GET", "path_params": {}, "query_params": {}},
            "depends_on": [],
            "description": "Count live schemas.",
            "required": True,
        }
    ]
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(api_plan)))
    assert failed.passed is False
    assert failed.error_type == "slot_scope_task_mismatch"

    relation_missing_zero = _relation_contract()
    relation_missing_zero["required_slots"][0].pop("zero_rows_semantics")
    failed = validator.validate(parse_semantic_ir_from_json_or_line_protocol(json.dumps(_plan_with_contract(relation_missing_zero))))
    assert failed.passed is False
    assert failed.error_type == "missing_zero_rows_semantics"


def test_evidence_contract_maps_count_date_relation_and_api_unavailable_states():
    count_contract = parse_answer_contract(_count_contract())
    count_states = evaluate_evidence_contract(
        count_contract,
        [
            {
                "pass_id": "t1",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 0}], "row_count": 1}}],
            }
        ],
    )
    assert count_states[0].status == "SATISFIED"
    assert count_states[0].count_values == [0]

    date_states = evaluate_evidence_contract(
        parse_answer_contract(_date_contract()),
        [
            {
                "pass_id": "t1",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"NAME": "Birthday Message"}], "row_count": 1}}],
            }
        ],
    )
    assert date_states[0].status == "PARTIAL"
    assert "PUBLISHEDAT" in date_states[0].missing_fields
    assert date_states[0].positive_assertion_allowed is False

    malformed_date_contract = _date_contract()
    malformed_date_contract["required_slots"][0]["required_fields"] = ["NAME", "STATUS"]
    malformed_date_contract["required_slots"][0]["acceptable_fallback_fields"] = []
    malformed_date_states = evaluate_evidence_contract(
        parse_answer_contract(malformed_date_contract),
        [
            {
                "pass_id": "t1",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "source_results": [
                    {
                        "source": "SQL",
                        "status": "SUCCESS",
                        "scope": "LOCAL_SNAPSHOT",
                        "result": {"rows": [{"NAME": "Birthday Message", "STATUS": "updated"}], "row_count": 1},
                    }
                ],
            }
        ],
    )
    assert malformed_date_states[0].status == "PARTIAL"
    assert malformed_date_states[0].date_values == []
    assert malformed_date_states[0].positive_assertion_allowed is False

    relation_states = evaluate_evidence_contract(
        parse_answer_contract(_relation_contract()),
        [
            {
                "pass_id": "t1",
                "status": "EMPTY",
                "scope": "LOCAL_SNAPSHOT",
                "source_results": [{"source": "SQL", "status": "EMPTY", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [], "row_count": 0}}],
            }
        ],
    )
    assert relation_states[0].status == "ZERO_ROWS"
    assert relation_states[0].positive_assertion_allowed is False

    api_unavailable = evaluate_evidence_contract(
        parse_answer_contract(_count_contract()),
        [{"pass_id": "t1", "status": "API_ERROR", "scope": "LIVE_API", "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API", "error": "unavailable"}]}],
    )
    assert api_unavailable[0].status == "API_UNAVAILABLE"
    assert isinstance(evidence_slot_state_to_dict(api_unavailable[0]), dict)
    assert isinstance(api_unavailable[0], EvidenceSlotState)


def test_evidence_contract_treats_successful_direct_concept_pass_as_satisfied():
    contract = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_concept",
                    "type": "CONCEPT",
                    "required": True,
                    "subject": "inactive journey",
                    "source_scope": "NONE",
                    "satisfied_by_tasks": ["t1"],
                    "zero_rows_semantics": "NOT_APPLICABLE",
                    "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
                }
            ],
            "optional_slots": [],
            "answer_style": "EXPLANATORY",
            "global_scope": "NONE",
            "contract_version": "v1",
        }
    )

    states = evaluate_evidence_contract(
        contract,
        [
            {
                "pass_id": "t1",
                "path": "DIRECT",
                "source": "DIRECT",
                "status": "SUCCESS",
                "scope": "NO_EVIDENCE_CONCEPT",
                "source_results": [
                    {
                        "source": "DIRECT",
                        "status": "SUCCESS",
                        "scope": "NO_EVIDENCE_CONCEPT",
                        "result": {"answer": "An inactive journey is a journey that is not currently active or running."},
                    }
                ],
            }
        ],
    )

    assert states[0].status == "SATISFIED"
    assert states[0].facts == [{"answer": "An inactive journey is a journey that is not currently active or running."}]


def test_evidence_contract_treats_empty_direct_concept_pass_as_concept_slot_available():
    contract = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_concept",
                    "type": "CONCEPT",
                    "required": True,
                    "subject": "inactive journey",
                    "source_scope": "NONE",
                    "satisfied_by_tasks": ["t1"],
                    "zero_rows_semantics": "NOT_APPLICABLE",
                    "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
                }
            ],
            "optional_slots": [],
            "answer_style": "EXPLANATORY",
            "global_scope": "NONE",
            "contract_version": "v1",
        }
    )

    states = evaluate_evidence_contract(
        contract,
        [
            {
                "pass_id": "t1",
                "path": "DIRECT",
                "source": "DIRECT",
                "status": "ERROR",
                "scope": "NO_EVIDENCE_CONCEPT",
                "source_results": [
                    {
                        "source": "DIRECT",
                        "status": "ERROR",
                        "scope": "NO_EVIDENCE_CONCEPT",
                        "result": {"answer": ""},
                        "error": "empty_direct_task_answer",
                    }
                ],
            }
        ],
    )

    assert states[0].status == "SATISFIED"
    assert states[0].source_scope == "NONE"
    assert states[0].facts == []


def test_answer_contract_from_plan_dict_does_not_infer_from_prompt():
    assert answer_contract_from_plan_dict({"route": "EVIDENCE", "tasks": []}) is None


def test_compact_count_slot_normalizes_mechanical_defaults():
    contract = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_count",
                    "type": "COUNT",
                    "required": True,
                    "subject": "schemas",
                    "source_scope": "LOCAL_SNAPSHOT",
                    "satisfied_by_tasks": ["t1"],
                    "required_fields": ["count"],
                    "if_missing": "FAIL_REQUIRED",
                    "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER",
                }
            ]
        }
    )

    slot = contract.required_slots[0]
    assert contract.contract_version == "v1"
    assert contract.answer_style == "COUNT_ONLY"
    assert contract.optional_slots == []
    assert slot.acceptable_fallback_fields == []
    assert slot.must_not_assert_positive_if_zero_rows is False


def test_compact_list_and_relation_slots_normalize_positive_assertion_guard():
    list_contract = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_list",
                    "type": "LIST",
                    "required": True,
                    "subject": "journeys",
                    "source_scope": "LOCAL_SNAPSHOT",
                    "satisfied_by_tasks": ["t1"],
                    "zero_rows_semantics": "NO_MATCH",
                    "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
                }
            ]
        }
    )
    relation_contract = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_relation",
                    "type": "RELATION",
                    "required": True,
                    "subject": "schema",
                    "object": "dataset",
                    "relation": "schema_to_dataset",
                    "source_scope": "LOCAL_SNAPSHOT",
                    "satisfied_by_tasks": ["t1"],
                    "zero_rows_semantics": "NO_MATCH",
                    "if_missing": "SCOPED_UNAVAILABLE_CAVEAT",
                }
            ]
        }
    )

    assert list_contract.answer_style == "LIST"
    assert list_contract.required_slots[0].must_not_assert_positive_if_zero_rows is True
    assert relation_contract.answer_style == "CAVEATED"
    assert relation_contract.required_slots[0].must_not_assert_positive_if_zero_rows is True


def test_compact_slot_still_requires_task_reference_and_source_scope():
    missing_task = parse_answer_contract(
        {
            "required_slots": [
                {
                    "slot_id": "s_count",
                    "type": "COUNT",
                    "required": True,
                    "subject": "schemas",
                    "source_scope": "LOCAL_SNAPSHOT",
                    "required_fields": ["count"],
                    "if_missing": "FAIL_REQUIRED",
                    "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER",
                }
            ]
        }
    )
    assert validate_answer_contract_shape(missing_task, task_ids=["t1"], route="EVIDENCE")["error_type"] == "missing_slot_task_reference"

    with pytest.raises(ValueError, match="source_scope"):
        parse_answer_contract(
            {
                "required_slots": [
                    {
                        "slot_id": "s_count",
                        "type": "COUNT",
                        "required": True,
                        "subject": "schemas",
                        "satisfied_by_tasks": ["t1"],
                        "required_fields": ["count"],
                        "if_missing": "FAIL_REQUIRED",
                        "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER",
                    }
                ]
            }
        )


def test_packaged_default_remains_sql_first_api_verify():
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
