from __future__ import annotations

import json

import pytest

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex
from dashagent.validators import SQLValidator
from dashagent.weak_model_semantic_slots import normalize_semantic_slots


def _schema(config: Config):
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    return db, schema


def test_typed_harness_state_declares_ordered_traceable_states():
    from dashagent.weak_model_harness_state import HarnessStateName, build_default_harness_state_machine

    states = build_default_harness_state_machine()

    assert [state.name for state in states][:3] == [
        HarnessStateName.INPUT,
        HarnessStateName.NORMALIZED_PROMPT,
        HarnessStateName.SEMANTIC_SLOTS,
    ]
    assert states[-1].name == HarnessStateName.FINAL_ANSWER
    assert all(state.trace_event and state.retry_policy for state in states)
    assert {HarnessStateName.SQL_VALIDATED, HarnessStateName.API_VALIDATED, HarnessStateName.CLAIMS_VERIFIED} <= {
        state.name for state in states
    }


def test_structured_output_schema_accepts_valid_slots_and_rejects_bad_enum():
    from dashagent.weak_model_output_schemas import parse_json_strict, validate_schema

    payload = parse_json_strict(
        json.dumps(
            {
                "intent": "COUNT",
                "domain": "JOURNEY",
                "entity_terms": [],
                "quoted_entities": [],
                "filters": [],
                "aggregation": "count_distinct",
                "relationship": {"needed": False, "left_entity": "", "right_entity": ""},
                "evidence_need": "sql_only",
                "confidence": 0.8,
            }
        )
    )
    result = validate_schema("SemanticSlots", payload)
    assert result.ok is True
    assert result.value["intent"] == "COUNT"

    bad = dict(payload)
    bad["intent"] = "MAKE_SQL_UP"
    rejected = validate_schema("SemanticSlots", bad)
    assert rejected.ok is False
    assert any("intent" in err for err in rejected.errors)
    assert rejected.repair_instructions


def test_recover_json_once_extracts_object_and_retry_prompt_names_schema():
    from dashagent.weak_model_output_schemas import recover_json_once, structured_retry_prompt

    recovered = recover_json_once("Here is JSON:\n```json\n{\"endpoint_id\":\"ups_audiences\",\"method\":\"GET\",\"params\":{},\"reason\":\"live\"}\n```")
    assert recovered["endpoint_id"] == "ups_audiences"
    prompt = structured_retry_prompt("APIPlanCandidate", ["method must be GET"])
    assert "APIPlanCandidate" in prompt
    assert "method must be GET" in prompt


def test_harness_assertions_block_unsafe_trajectory_states():
    from dashagent.weak_model_harness_assertions import evaluate_harness_assertions

    no_tool = evaluate_harness_assertions(
        {
            "prompt": "How many journeys are active?",
            "answer": "There are 3 active journeys.",
            "semantic_slots": {"intent": "COUNT", "domain": "JOURNEY", "evidence_need": "sql_only"},
            "tool_calls": [],
            "evidence": {},
        }
    )
    assert no_tool.failed("data_question_requires_tool")

    unresolved_api = evaluate_harness_assertions(
        {
            "prompt": "Show live tag details.",
            "semantic_slots": {"intent": "DETAIL", "domain": "TAG", "evidence_need": "api_only"},
            "api_candidate": {"endpoint_id": "tag_detail", "method": "GET", "path": "/tags/{tag_id}"},
            "tool_calls": [],
        }
    )
    assert unresolved_api.failed("api_no_unresolved_path_params")

    live_empty = evaluate_harness_assertions(
        {
            "prompt": "Show live datasets.",
            "semantic_slots": {"intent": "LIST", "domain": "DATASET", "evidence_need": "api_only"},
            "api_evidence": {"outcome": "live_empty"},
            "answer": "There is no data in Adobe.",
            "tool_calls": [{"kind": "api_call"}],
        }
    )
    assert live_empty.failed("live_empty_not_global_no_data")


def test_schema_retriever_compacts_context_and_links_values(tiny_project):
    from dashagent.weak_sql_schema_retriever import retrieve_weak_sql_schema_context

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots({}, prompt="When was the journey 'Birthday Message' published?")
    context = retrieve_weak_sql_schema_context(
        "When was the journey 'Birthday Message' published?",
        schema,
        slots,
        max_tables=3,
        max_columns_per_table=6,
        max_join_hints=4,
    )

    assert len(context["retrieved_tables"]) <= 3
    assert all(len(cols) <= 6 for cols in context["retrieved_columns"].values())
    assert len(context["join_candidates"]) <= 4
    assert context["retrieved_tables"][0] == "dim_campaign"
    assert context["value_links"][0]["value"] == "Birthday Message"
    db.close()


def test_compile_semantic_slots_accepts_compact_retrieval_limits(tiny_project):
    from dashagent.semantic_slot_compiler import compile_semantic_slots

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots({}, prompt="When was the journey 'Birthday Message' published?")
    compiled = compile_semantic_slots(
        slots,
        schema,
        EndpointCatalog(tiny_project),
        SQLValidator(schema),
        prompt="When was the journey 'Birthday Message' published?",
        enhanced_sql=True,
        retrieval_limits={"max_tables": 2, "max_columns_per_table": 5, "max_join_hints": 2, "max_skeletons": 1},
    )

    assert compiled["enhanced_sql"] is True
    assert len(compiled["schema_context"]["retrieved_tables"]) <= 2
    assert all(len(columns) <= 5 for columns in compiled["schema_context"]["retrieved_columns"].values())
    assert len(compiled["schema_context"]["join_candidates"]) <= 2
    assert len(compiled["sql_skeletons"]) <= 1
    db.close()


def test_skeleton_retriever_has_generic_group_and_recent_skeletons():
    from dashagent.weak_sql_skeleton_retriever import SQL_SKELETONS, retrieve_sql_skeletons

    skeleton_ids = {item["skeleton_id"] for item in SQL_SKELETONS}
    assert {"group_by_count", "recent_items", "list_entities"} <= skeleton_ids
    retrieved = retrieve_sql_skeletons({"intent": "COUNT", "aggregation": "count", "relationship": {"needed": False}}, limit=3)
    serialized = json.dumps(retrieved).lower()
    assert "query_id" not in serialized
    assert "gold" not in serialized


def test_sql_unit_tester_reports_critical_failures_for_wrong_aggregation():
    from dashagent.weak_sql_unit_tester import run_sql_semantic_unit_tests

    slots = normalize_semantic_slots({}, prompt="How many journeys are active?")
    context = {"retrieved_tables": ["dim_campaign"], "column_roles": {"dim_campaign": {"id": ["campaign_id"], "status": ["STATE"]}}}
    plan = {
        "answer_intent": "COUNT",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["NAME"],
        "filters": [],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": "*"},
    }

    result = run_sql_semantic_unit_tests("How many journeys are active?", slots, plan, "", context)
    assert result["passed"] is False
    assert "aggregation_test" in result["failed_tests"]
    assert "aggregation_test" in result["critical_failures"]


def test_candidate_ranker_prefers_valid_useful_compact_candidate():
    from dashagent.weak_sql_candidate_ranker import rank_sql_candidates

    ranked = rank_sql_candidates(
        "How many journeys are active?",
        [
            {"candidate_id": "bad", "sql": "SELECT NAME FROM dim_campaign", "sql_unit_tests": {"passed": False, "semantic_score": 0.4}, "validation": {"ok": True}},
            {"candidate_id": "good", "sql": "SELECT COUNT(DISTINCT campaign_id) AS count FROM dim_campaign", "sql_unit_tests": {"passed": True, "semantic_score": 1.0}, "validation": {"ok": True}, "execution_probe": {"probe_ok": True, "row_count": 1}},
        ],
    )

    assert ranked["selected_candidate_id"] == "good"
    assert ranked["ranking"][0]["candidate_id"] == "good"
    assert ranked["ranking_features"]["good"]["unit_tests_passed"] is True


def test_repair_loop_repairs_slots_from_unit_test_hints(tiny_project):
    from dashagent.weak_sql_repair_loop import repair_slots_from_unit_feedback, run_weak_sql_repair_loop

    prompt = "How many journeys are active?"
    slots = normalize_semantic_slots({}, prompt=prompt)
    slots["aggregation"] = "none"
    repaired = repair_slots_from_unit_feedback(slots, ["Use count or count_distinct aggregation for count prompts."], prompt)

    assert repaired["aggregation"] in {"count", "count_distinct"}

    db, schema = _schema(tiny_project)
    result = run_weak_sql_repair_loop(prompt, slots, schema, EndpointCatalog(tiny_project), SQLValidator(schema), max_repair_rounds=1)
    assert result["repair_attempts"] <= 1
    assert result["final_state"] in {"sql_candidate_ready", "safe_no_sql"}
    db.close()


def test_harness_variants_are_registered_shadow_only():
    from scripts.run_weak_model_lift_eval import WEAK_MODEL_VARIANTS

    assert {
        "weak_harness_slots_only_v1",
        "weak_harness_schema_retrieval_v1",
        "weak_harness_unit_tested_sql_v1",
        "weak_harness_repair_loop_v1",
        "weak_harness_balanced_sql_api_answer_v1",
        "weak_harness_full_v1",
        "weak_harness_answer_v1_style_preserve",
        "weak_harness_answer_evidence_bullets",
        "weak_harness_answer_slot_template",
        "weak_harness_answer_api_primary_when_api_scores_better",
        "weak_harness_compact_context_v1",
        "weak_harness_skip_repair_when_unit_pass_v1",
        "weak_harness_compact_trace_v1",
        "weak_harness_answer_grounding_compact_v1",
        "weak_harness_answer_and_efficiency_v2",
    } <= set(WEAK_MODEL_VARIANTS)
