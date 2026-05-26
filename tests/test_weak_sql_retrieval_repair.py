from __future__ import annotations

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


def test_schema_retriever_maps_domain_aliases_and_timestamp_roles(tiny_project):
    from dashagent.weak_sql_schema_retriever import retrieve_weak_sql_schema_context

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots({}, prompt="When was the journey 'Welcome Journey' published?")
    context = retrieve_weak_sql_schema_context("When was the journey 'Welcome Journey' published?", schema, slots)

    assert context["retrieved_tables"][0] == "dim_campaign"
    assert "lastdeployedtime" in {column.lower() for column in context["timestamp_candidates"]["dim_campaign"]["published"]}
    assert context["column_roles"]["dim_campaign"]["name"]
    assert context["value_links"][0]["semantic_field"] == "name"
    db.close()


def test_schema_retriever_returns_known_join_hints_only(tiny_project):
    from dashagent.weak_sql_schema_retriever import retrieve_weak_sql_schema_context

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots({}, prompt="List segment audiences connected to a destination")
    context = retrieve_weak_sql_schema_context("List segment audiences connected to a destination", schema, slots)

    assert all(item["left_table"] in schema.tables and item["right_table"] in schema.tables for item in context["join_candidates"])
    db.close()


def test_sql_skeleton_retriever_returns_generic_non_gold_examples():
    from dashagent.weak_sql_skeleton_retriever import retrieve_sql_skeletons

    skeletons = retrieve_sql_skeletons({"intent": "COUNT", "domain": "JOURNEY"})

    assert skeletons[0]["skeleton_id"] in {"count_entity", "count_distinct_entity"}
    serialized = str(skeletons).lower()
    assert "query_id" not in serialized
    assert "example_" not in serialized
    assert "gold" not in serialized


def test_sql_unit_tester_rejects_wrong_table_missing_filter_and_timestamp():
    from dashagent.weak_sql_unit_tester import run_sql_semantic_unit_tests

    slots = normalize_semantic_slots({}, prompt="When was the journey 'Welcome Journey' published?")
    context = {
        "retrieved_tables": ["dim_campaign"],
        "timestamp_candidates": {"dim_campaign": {"published": ["LASTDEPLOYEDTIME"]}},
        "column_roles": {"dim_campaign": {"name": ["NAME"], "timestamp": ["LASTDEPLOYEDTIME"]}},
        "value_links": [{"semantic_field": "name", "value": "Welcome Journey"}],
    }

    wrong = {
        "answer_intent": "DATE",
        "primary_table": "dim_segment",
        "tables_needed": ["dim_segment"],
        "columns_needed": ["UPDATEDTIME"],
        "filters": [],
        "aggregation": {"type": "none", "table": "dim_segment", "column": "*"},
    }
    result = run_sql_semantic_unit_tests("When was the journey 'Welcome Journey' published?", slots, wrong, "", context)

    assert result["passed"] is False
    assert {"table_test", "filter_test", "timestamp_test"} & set(result["failed_tests"])


def test_enhanced_compiler_repairs_published_date_filter_without_suppressing_api(tiny_project):
    from dashagent.semantic_slot_compiler import compile_semantic_slots

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots({}, prompt="When was the journey 'Welcome Journey' published?")
    slots["evidence_need"] = "sql_primary_api_verify"
    compiled = compile_semantic_slots(
        slots,
        schema,
        EndpointCatalog(tiny_project),
        SQLValidator(schema),
        prompt="When was the journey 'Welcome Journey' published?",
        enhanced_sql=True,
        repair_rounds=1,
    )

    assert compiled["sql_candidates"]
    sql = compiled["sql_candidates"][0]["sql"]
    assert "lastdeployedtime" in sql.lower()
    assert "STATE" not in sql
    assert compiled["sql_candidates"][0]["sql_unit_tests"]["passed"] is True
    assert compiled["api_candidates"]
    db.close()


def test_weak_slot_intent_ignores_count_word_inside_quoted_schema_name():
    slots = normalize_semantic_slots({}, prompt="List all datasets that use the schema 'hkg_adls_profile_count_history'.")

    assert slots["intent"] == "RELATIONSHIP"


def test_sql_improvement_variants_are_shadow_only():
    from scripts.run_weak_model_lift_eval import WEAK_MODEL_VARIANTS

    assert "weak_scaffold_sql_retrieval_repair_v1" in WEAK_MODEL_VARIANTS
    assert "weak_scaffold_balanced_sql_api_v2" in WEAK_MODEL_VARIANTS
