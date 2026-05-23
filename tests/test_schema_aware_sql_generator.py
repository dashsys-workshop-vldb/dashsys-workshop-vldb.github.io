from __future__ import annotations

import inspect
from dataclasses import replace

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.planner import StrategyPlanner
from dashagent.router import RoutingDecision
from dashagent.schema_aware_sql_generator import (
    generate_schema_aware_sql_candidates,
    validate_schema_aware_sql,
)
from dashagent.schema_index import JoinHint, SchemaIndex
from dashagent.sql_templates import find_sql_template
from dashagent.validators import SQLValidator


def test_template_still_wins_when_high_confidence(tiny_project: Config):
    schema = _campaign_template_schema()
    planner = StrategyPlanner(schema, replace(tiny_project, enable_schema_aware_sql_fallback=True))
    query = "List all journeys"
    routing = RoutingDecision("SQL_ONLY", "JOURNEY_CAMPAIGN", 0.9, "test", ["dim_campaign"], [])
    metadata = {"selected_tables": ["dim_campaign"], "domain_type": "JOURNEY_CAMPAIGN"}

    template = find_sql_template(query, schema)
    plan = planner.create_plan(query, routing, metadata, "SQL_FIRST_API_VERIFY")

    sql_step = next(step for step in plan.steps if step.action == "sql")
    assert template is not None
    assert sql_step.family == template.family
    assert "schema-aware SQL fallback" not in plan.rationale
    assert not any("schema-aware SQL fallback selected" in action for action in plan.optimizer_actions)


def test_schema_aware_fallback_activates_on_template_miss(tiny_project: Config):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    planner = StrategyPlanner(schema, replace(tiny_project, enable_schema_aware_sql_fallback=True))
    query = "How many unique audiences are in the local snapshot?"
    routing = RoutingDecision("SQL_ONLY", "SEGMENT_AUDIENCE", 0.7, "test", ["dim_segment"], [])
    metadata = {"selected_tables": ["dim_segment"], "domain_type": "SEGMENT_AUDIENCE"}

    plan = planner.create_plan(query, routing, metadata, "SQL_FIRST_API_VERIFY")

    sql_step = next(step for step in plan.steps if step.action == "sql")
    assert sql_step.family == "schema_aware_sql_fallback"
    assert "COUNT(DISTINCT" in (sql_step.sql or "")
    assert SQLValidator(schema).validate(sql_step.sql or "").ok is True


def test_count_distinct_generated_for_unique_id_count(tiny_project: Config):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    result = generate_schema_aware_sql_candidates(
        "How many unique segments are there?",
        schema,
        selected_tables=["dim_segment"],
    )

    candidate = result.selected_candidate
    assert candidate is not None
    assert "COUNT(DISTINCT" in candidate.sql
    assert candidate.validation["ok"] is True


def test_join_candidate_uses_known_bridge_table_only():
    schema = _relationship_schema()
    result = generate_schema_aware_sql_candidates(
        "List segment audiences connected to destinations",
        schema,
        selected_tables=["dim_segment", "dim_target"],
    )

    candidate = result.selected_candidate
    assert candidate is not None
    assert candidate.candidate_id == "schema_join_path"
    assert "hkg_br_segment_target" in candidate.sql
    assert "JOIN" in candidate.sql
    assert candidate.validation["ok"] is True
    assert all(edge["left_table"] in schema.tables and edge["right_table"] in schema.tables for edge in candidate.join_path)


def test_unknown_tables_and_columns_are_rejected():
    schema = _relationship_schema()

    bad_table = validate_schema_aware_sql("SELECT * FROM made_up_table", schema)
    bad_column = validate_schema_aware_sql('SELECT "missing_col" FROM "dim_segment"', schema)

    assert bad_table["ok"] is False
    assert bad_table["unknown_tables"] == ["made_up_table"]
    assert bad_column["ok"] is False
    assert "missing_col" in bad_column["unknown_columns"]


def test_destructive_sql_is_rejected():
    schema = _relationship_schema()

    result = validate_schema_aware_sql("DROP TABLE dim_segment", schema)

    assert result["ok"] is False
    assert result["destructive_sql_detected"] is True or result["validator_ok"] is False


def test_schema_aware_generator_has_no_query_id_or_gold_hacks():
    import dashagent.schema_aware_sql_generator as generator

    source = inspect.getsource(generator)
    assert "query_id" not in source
    assert "gold" not in source.lower()


def _campaign_template_schema() -> SchemaIndex:
    return SchemaIndex(
        tables={
            "dim_campaign": {
                "columns": [
                    {"name": "campaign_id"},
                    {"name": "name"},
                    {"name": "state"},
                    {"name": "updatedtime"},
                    {"name": "lastdeployedtime"},
                ],
                "id_columns": ["campaign_id"],
                "primary_like_id": "campaign_id",
                "is_bridge": False,
            }
        }
    )


def _relationship_schema() -> SchemaIndex:
    tables = {
        "dim_segment": {
            "columns": [{"name": "segment_id"}, {"name": "name"}, {"name": "totalmembers"}],
            "id_columns": ["segment_id"],
            "primary_like_id": "segment_id",
            "is_bridge": False,
        },
        "hkg_br_segment_target": {
            "columns": [{"name": "segment_id"}, {"name": "target_id"}],
            "id_columns": ["segment_id", "target_id"],
            "primary_like_id": "segment_id",
            "is_bridge": True,
        },
        "dim_target": {
            "columns": [{"name": "target_id"}, {"name": "name"}, {"name": "state"}],
            "id_columns": ["target_id"],
            "primary_like_id": "target_id",
            "is_bridge": False,
        },
    }
    return SchemaIndex(
        tables=tables,
        bridge_tables=["hkg_br_segment_target"],
        join_hints=[
            JoinHint("dim_segment", "segment_id", "hkg_br_segment_target", "segment_id", 0.98, "Segment bridge."),
            JoinHint("dim_target", "target_id", "hkg_br_segment_target", "target_id", 0.98, "Target bridge."),
        ],
    )
