from __future__ import annotations

import json

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex


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


def _context(tiny_project: Config):
    from dashagent.llm_sql_context_builder import build_llm_sql_context

    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    context = build_llm_sql_context("List all campaigns", schema, EndpointCatalog(tiny_project))
    db.close()
    return context, EndpointCatalog(tiny_project)


def test_evidence_source_planner_requires_json_schema(tiny_project):
    from dashagent.llm_evidence_source_planner import plan_evidence_source

    context, catalog = _context(tiny_project)
    client = FakeJsonClient(
        [
            json.dumps(
                {
                    "question_type": "list",
                    "needs_local_sql": True,
                    "needs_live_api": False,
                    "sql_reason": "campaigns are available in local schema",
                    "api_reason": "",
                    "local_tables_that_may_answer": ["dim_campaign"],
                    "api_endpoints_that_may_answer": [],
                    "preferred_first_tool": "execute_sql",
                    "confidence": 0.9,
                }
            )
        ]
    )

    plan = plan_evidence_source("List all campaigns", context, catalog, client)

    assert plan["ok"] is True
    assert plan["plan"]["preferred_first_tool"] == "execute_sql"
    assert plan["plan"]["needs_local_sql"] is True
    assert client.calls


def test_tool_choice_validator_rejects_api_when_sql_required(tiny_project):
    from dashagent.llm_tool_choice_validator import validate_tool_choice_plan

    context, catalog = _context(tiny_project)
    result = validate_tool_choice_plan(
        "List all campaigns",
        {
            "question_type": "list",
            "needs_local_sql": False,
            "needs_live_api": True,
            "local_tables_that_may_answer": [],
            "api_endpoints_that_may_answer": ["journey_list"],
            "preferred_first_tool": "call_api",
            "confidence": 0.8,
        },
        context,
        catalog,
    )

    assert result["ok"] is False
    assert result["rejection_reason"] == "sql_likely_required_api_chosen"
    assert result["evidence_source_that_should_have_been_considered"] == "local_sql_required"
    assert result["high_confidence_sql_required"] is True


def test_tool_choice_validator_rejects_no_tool_for_data_question(tiny_project):
    from dashagent.llm_tool_choice_validator import validate_tool_choice_plan

    context, catalog = _context(tiny_project)
    result = validate_tool_choice_plan(
        "How many campaigns are there?",
        {"needs_local_sql": False, "needs_live_api": False, "preferred_first_tool": "none"},
        context,
        catalog,
    )

    assert result["ok"] is False
    assert result["rejection_reason"] == "tool_required"


def test_tool_choice_validator_blocks_unresolved_api_path_params(tiny_project):
    from dashagent.llm_tool_choice_validator import validate_tool_choice_plan

    context, catalog = _context(tiny_project)
    result = validate_tool_choice_plan(
        "Get batch details",
        {
            "needs_local_sql": False,
            "needs_live_api": True,
            "preferred_first_tool": "call_api",
            "api_endpoints_that_may_answer": ["catalog_batch_detail"],
        },
        context,
        catalog,
    )

    assert result["ok"] is False
    assert result["rejection_reason"] == "unresolved_api_path_param"


def test_sql_first_high_confidence_variant_runs_sql_after_api_biased_plan(tiny_project):
    from dashagent.pure_llm_tool_agent import SQL_FIRST_WHEN_VALIDATOR_HIGH_CONFIDENCE_V1, run_pure_llm_tool_agent_variant

    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    client = FakeJsonClient(
        [
            json.dumps({"answer_intent": "LIST", "needs_sql": False, "needs_api": True, "candidate_endpoints": ["journey_list"]}),
            json.dumps(
                {
                    "question_type": "list",
                    "needs_local_sql": False,
                    "needs_live_api": True,
                    "sql_reason": "",
                    "api_reason": "journey endpoint exists",
                    "local_tables_that_may_answer": [],
                    "api_endpoints_that_may_answer": ["journey_list"],
                    "preferred_first_tool": "call_api",
                    "confidence": 0.7,
                }
            ),
            json.dumps(
                {
                    "question_type": "list",
                    "needs_local_sql": False,
                    "needs_live_api": True,
                    "preferred_first_tool": "call_api",
                    "confidence": 0.7,
                }
            ),
            json.dumps(
                {
                    "answer_intent": "LIST",
                    "primary_entity": "campaigns",
                    "primary_table": "dim_campaign",
                    "tables_needed": ["dim_campaign"],
                    "columns_needed": ["campaign_id", "name"],
                    "join_needed": False,
                    "join_path_reason": "",
                    "filters": [],
                    "aggregation": {"type": "none", "table": "dim_campaign", "column": "*"},
                    "order_by": [],
                    "limit": 50,
                    "confidence": 0.8,
                }
            ),
            json.dumps({"answer": "The SQL evidence returned local campaign rows.", "claims": []}),
        ]
    )

    result = run_pure_llm_tool_agent_variant(
        "List all campaigns",
        variant=SQL_FIRST_WHEN_VALIDATOR_HIGH_CONFIDENCE_V1,
        db=db,
        schema_index=schema,
        endpoint_catalog=EndpointCatalog(tiny_project),
        llm_client=client,
    )

    step_kinds = [step["kind"] for step in result["trajectory"]["steps"]]
    assert "evidence_source_plan" in step_kinds
    assert "sql_call" in step_kinds
    assert result["trace_assertions"]["sql_validation_ok"] is True
    assert result["trace_assertions"]["api_endpoint_validation_ok"] is False
    assert result["unsupported_claim_count"] == 0
    db.close()
