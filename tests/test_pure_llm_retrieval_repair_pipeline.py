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
        return {"ok": True, "content": content, "usage": {"total_tokens": 7}}


def _schema(config: Config):
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    return db, schema


def test_schema_retriever_maps_business_terms_and_timestamp_roles(tiny_project):
    from dashagent.pure_llm_schema_retriever import retrieve_schema_context

    db, schema = _schema(tiny_project)
    context = retrieve_schema_context("When was the journey 'Welcome Journey' published?", schema, EndpointCatalog(tiny_project))

    assert context["retrieved_tables"][0]["table"] == "dim_campaign"
    assert "lastdeployedtime" in context["semantic_roles"]["published_timestamp_columns"]["dim_campaign"]
    assert context["value_links"][0]["value"] == "Welcome Journey"
    assert context["value_links"][0]["candidate_columns"][0]["column"] == "name"
    db.close()


def test_dynamic_example_retriever_returns_skeletons_without_gold_leakage(tiny_project):
    from dashagent.pure_llm_schema_retriever import retrieve_schema_context
    from dashagent.pure_llm_sql_example_retriever import retrieve_sql_examples

    db, schema = _schema(tiny_project)
    context = retrieve_schema_context("How many journeys are published?", schema, EndpointCatalog(tiny_project))
    examples = retrieve_sql_examples("How many journeys are published?", context, limit=3)

    assert examples
    assert all("query_id" not in json.dumps(example).lower() for example in examples)
    assert all("gold" not in json.dumps(example).lower() for example in examples)
    assert any("COUNT" in example["sql_skeleton"].upper() for example in examples)
    db.close()


def test_text_to_sql_pipeline_repairs_wrong_timestamp_plan(tiny_project):
    from dashagent.pure_llm_text_to_sql_pipeline import run_pure_llm_text_to_sql_pipeline

    db, schema = _schema(tiny_project)
    bad_candidate = {
        "candidates": [
            {
                "candidate_id": "bad_updated",
                "answer_intent": "DATE",
                "primary_table": "dim_campaign",
                "tables_needed": ["dim_campaign"],
                "columns_needed": ["status"],
                "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Welcome Journey"}],
                "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
                "order_by": [],
                "limit": 50,
                "reason": "bad timestamp",
                "confidence": 0.5,
            }
        ]
    }
    repaired = {
        "answer_intent": "DATE",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["lastdeployedtime"],
        "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Welcome Journey"}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
        "order_by": [],
        "limit": 50,
        "reason": "published timestamps use deployment fields",
        "confidence": 0.9,
    }
    client = FakeJsonClient([json.dumps(bad_candidate), json.dumps({"semantically_matches_prompt": False, "repair_suggestion": "use lastdeployedtime"}), json.dumps(repaired)])

    result = run_pure_llm_text_to_sql_pipeline(
        "When was the journey 'Welcome Journey' published?",
        db,
        schema,
        EndpointCatalog(tiny_project),
        SQLValidator(schema),
        llm_client=client,
        review_repair=True,
        execution_probe=True,
        evidence_grounding=True,
    )

    assert result["ok"] is True
    assert result["selected_sql"]
    assert "lastdeployedtime" in result["selected_sql"].lower()
    assert result["sql_evidence"]["sql_executed"] is True
    assert result["sql_evidence"]["timestamp_values"] == ["2026-01-01"]
    db.close()


def test_retrieval_repair_variants_are_shadow_only():
    from dashagent.pure_llm_tool_agent import (
        EVIDENCE_GROUNDED_SQL_AGENT_V1,
        EXECUTION_GUIDED_SQL_AGENT_V1,
        FULL_RETRIEVAL_REPAIR_GROUNDED_PURE_LLM_V1,
        RETRIEVED_SCHEMA_SQL_AGENT_V1,
        REVIEWED_SQL_REPAIR_AGENT_V1,
        PURE_LLM_TOOL_AGENT_VARIANTS,
        pure_llm_baseline_definitions,
    )

    for variant in (
        RETRIEVED_SCHEMA_SQL_AGENT_V1,
        REVIEWED_SQL_REPAIR_AGENT_V1,
        EXECUTION_GUIDED_SQL_AGENT_V1,
        EVIDENCE_GROUNDED_SQL_AGENT_V1,
        FULL_RETRIEVAL_REPAIR_GROUNDED_PURE_LLM_V1,
    ):
        assert variant in PURE_LLM_TOOL_AGENT_VARIANTS
        definition = next(item for item in pure_llm_baseline_definitions() if item["variant"] == variant)
        assert definition["status"] == "shadow_diagnostic"
