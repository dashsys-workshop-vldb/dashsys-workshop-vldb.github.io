from __future__ import annotations

import json

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex
from dashagent.validators import SQLValidator


class FakeJsonClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "fake-model"

    def generate(self, system_prompt, user_prompt, tools=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "tools": tools})
        content = self.responses.pop(0) if self.responses else "{}"
        return {"ok": True, "content": content, "usage": {"total_tokens": 5}}


def _schema(config: Config):
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    return db, schema


def _context(config: Config, prompt: str):
    from dashagent.llm_sql_context_builder import build_llm_sql_context

    db, schema = _schema(config)
    context = build_llm_sql_context(prompt, schema, EndpointCatalog(config))
    db.close()
    return context


def test_sql_semantic_verifier_rejects_date_plan_without_published_timestamp(tiny_project):
    from dashagent.llm_sql_semantic_verifier import verify_sql_plan_semantics

    context = _context(tiny_project, "When was the journey 'Birthday Message' published?")
    plan = {
        "answer_intent": "DATE",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["updatedtime"],
        "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Birthday Message"}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
    }

    result = verify_sql_plan_semantics("When was the journey 'Birthday Message' published?", {}, plan, context, "DATE")

    assert result["ok"] is False
    assert any("published timestamp" in error.lower() for error in result["errors"])
    assert result["semantic_score"] < 1.0


def test_sql_semantic_verifier_accepts_published_timestamp_filter(tiny_project):
    from dashagent.llm_sql_semantic_verifier import verify_sql_plan_semantics

    context = _context(tiny_project, "When was the journey 'Birthday Message' published?")
    plan = {
        "answer_intent": "DATE",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["lastdeployedtime"],
        "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Birthday Message"}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
    }

    result = verify_sql_plan_semantics("When was the journey 'Birthday Message' published?", {}, plan, context, "DATE")

    assert result["ok"] is True
    assert result["semantic_score"] == 1.0


def test_sql_semantic_verifier_requires_list_id_or_name_columns(tiny_project):
    from dashagent.llm_sql_semantic_verifier import verify_sql_plan_semantics

    context = _context(tiny_project, "List all journeys")
    plan = {
        "answer_intent": "LIST",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["lastdeployedtime"],
        "filters": [{"table": "dim_campaign", "column": "campaign_id", "operator": "equals", "value": None}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
    }

    result = verify_sql_plan_semantics("List all journeys", {}, plan, context, "LIST")

    assert result["ok"] is False
    assert "ID or name" in " ".join(result["errors"])
    assert any("NULL filter" in warning for warning in result["warnings"])


def test_sql_semantic_verifier_rejects_wrong_entity_table(tiny_project):
    from dashagent.llm_sql_semantic_verifier import verify_sql_plan_semantics

    context = _context(tiny_project, "List all journeys")
    plan = {
        "answer_intent": "LIST",
        "primary_table": "dim_segment",
        "tables_needed": ["dim_segment"],
        "columns_needed": ["segment_id", "name"],
        "filters": [],
        "aggregation": {"type": "none", "table": "dim_segment", "column": ""},
    }

    result = verify_sql_plan_semantics("List all journeys", {}, plan, context, "LIST")

    assert result["ok"] is False
    assert any("dim_campaign" in error for error in result["errors"])


def test_sql_semantic_repair_loop_uses_semantic_feedback(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("When was the journey 'Birthday Message' published?", schema, EndpointCatalog(tiny_project))
    bad_plan = {
        "answer_intent": "DATE",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["updatedtime"],
        "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Birthday Message"}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
    }
    repaired_plan = {**bad_plan, "columns_needed": ["lastdeployedtime"]}
    client = FakeJsonClient([json.dumps(bad_plan), json.dumps(repaired_plan)])

    result = run_sql_repair_loop(
        "When was the journey 'Birthday Message' published?",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        max_repair_rounds=2,
        structured_sql_plan=True,
        semantic_verify=True,
    )

    assert result["ok"] is True
    assert result["semantic_repair_attempted"] is True
    assert result["semantic_repair_success"] is True
    assert result["final_semantic_score"] == 1.0
    assert '"lastdeployedtime"' in result["sql"]
    db.close()


def test_sql_result_answer_grounder_falls_back_when_sql_result_ignored():
    from dashagent.llm_sql_result_answer_grounder import ground_sql_result_answer

    result = ground_sql_result_answer(
        "List all journeys",
        "The available tool evidence does not contain enough supported data to answer.",
        {"ok": True, "rows": [{"campaign_id": "c1", "name": "Birthday Message"}], "row_count": 1},
        answer_intent="LIST",
    )

    assert result["sql_result_used_in_answer"] is True
    assert result["fallback_to_sql_result_answer"] is True
    assert "Birthday Message" in result["answer"]
    assert result["unsupported_claim_count"] == 0


def test_sql_result_answer_grounder_zero_rows_is_explicit():
    from dashagent.llm_sql_result_answer_grounder import ground_sql_result_answer

    result = ground_sql_result_answer(
        "Give me inactive journeys",
        "No answer.",
        {"ok": True, "rows": [], "row_count": 0},
        answer_intent="LIST",
    )

    assert "no matching records" in result["answer"].lower()
    assert result["unsupported_claim_count"] == 0


def test_tool_choice_validator_rejects_api_only_for_local_dataflow_ids(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_tool_choice_validator import validate_tool_choice_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("Show me failed dataflow IDs", schema, EndpointCatalog(tiny_project))
    result = validate_tool_choice_plan(
        "Show me failed dataflow IDs",
        {
            "needs_local_sql": False,
            "needs_live_api": True,
            "preferred_first_tool": "call_api",
            "api_endpoints_that_may_answer": ["export_batch_failed"],
        },
        context,
        EndpointCatalog(tiny_project),
    )

    assert result["ok"] is False
    assert result["rejection_reason"] == "sql_likely_required_api_chosen"
    assert result["high_confidence_sql_required"] is True
    db.close()


def test_semantic_variants_are_shadow_only(tiny_project):
    from dashagent.pure_llm_tool_agent import (
        CONSERVATIVE_SQL_FIRST_SEMANTIC_V1,
        PURE_LLM_TOOL_AGENT_VARIANTS,
        pure_llm_baseline_definitions,
    )

    assert CONSERVATIVE_SQL_FIRST_SEMANTIC_V1 in PURE_LLM_TOOL_AGENT_VARIANTS
    definition = next(item for item in pure_llm_baseline_definitions() if item["variant"] == CONSERVATIVE_SQL_FIRST_SEMANTIC_V1)
    assert definition["status"] == "shadow_diagnostic"
