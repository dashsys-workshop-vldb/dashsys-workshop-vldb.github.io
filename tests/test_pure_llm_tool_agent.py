from __future__ import annotations

import json
from pathlib import Path

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex
from dashagent.validators import APIValidator, SQLValidator


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
        return {"ok": True, "content": content, "usage": {"total_tokens": 11}}


def _schema(tiny_project: Config) -> tuple[DuckDBDatabase, SchemaIndex]:
    db = DuckDBDatabase(tiny_project)
    return db, SchemaIndex.build(db)


def test_llm_sql_context_builder_retrieves_relevant_tables_and_join_hints(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many campaigns are published?", schema, EndpointCatalog(tiny_project))

    assert context["top_tables"][0]["table"] == "dim_campaign"
    assert "campaign_id" in context["primary_id_columns"]["dim_campaign"]
    assert "SELECT only" in " ".join(context["sql_rules"])
    assert all(table["table"] in schema.tables for table in context["top_tables"])
    db.close()


def test_llm_tool_agent_prompt_builders_require_json_only():
    from dashagent.llm_tool_agent_prompts import build_planning_prompt, parse_json_object

    prompt = build_planning_prompt(
        "How many campaigns?",
        {"top_tables": [{"table": "dim_campaign"}], "endpoint_candidates": []},
    )

    assert "JSON only" in prompt.system_prompt
    assert '"needs_sql"' in prompt.system_prompt
    assert parse_json_object('```json\n{"needs_sql": true}\n```') == {"needs_sql": True}


def test_llm_sql_repair_loop_never_executes_invalid_sql_before_repair(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many campaigns?", schema, EndpointCatalog(tiny_project))
    client = FakeJsonClient(
        [
            json.dumps({"sql": "SELECT COUNT(*) AS count FROM missing_table", "tables_used": ["missing_table"]}),
            json.dumps({"sql": "SELECT COUNT(*) AS count FROM dim_campaign", "tables_used": ["dim_campaign"]}),
        ]
    )

    result = run_sql_repair_loop(
        "How many campaigns?",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        max_repair_rounds=2,
    )

    assert result["ok"] is True
    assert result["sql"] == "SELECT COUNT(*) AS count FROM dim_campaign"
    assert result["repair_rounds"] == 1
    assert result["attempts"][0]["executed"] is False
    assert result["attempts"][0]["validation"]["ok"] is False
    assert result["execution_result"]["row_count"] == 1
    db.close()


def test_llm_api_tool_guard_blocks_freeform_and_allows_catalog_get(tiny_project):
    from dashagent.llm_api_tool_guard import validate_llm_api_candidate

    catalog = EndpointCatalog(tiny_project)
    validator = APIValidator(catalog)

    rejected = validate_llm_api_candidate(
        {"url": "https://example.invalid/freeform", "method": "GET"},
        catalog,
        validator,
    )
    accepted = validate_llm_api_candidate(
        {"endpoint_id": "ups_audiences", "method": "GET", "params": {"limit": 5}},
        catalog,
        validator,
    )

    assert rejected["ok"] is False
    assert "endpoint_id" in rejected["rejection_reason"]
    assert accepted["ok"] is True
    assert accepted["validated_api_call"]["url"] == "/data/core/ups/audiences"


def test_evidence_locked_answer_rejects_unsupported_number(tiny_project):
    from dashagent.llm_evidence_locked_answer import evidence_locked_answer

    client = FakeJsonClient([json.dumps({"answer": "There are 99 campaigns.", "claims": []})])
    result = evidence_locked_answer(
        "How many campaigns?",
        [{"source": "sql", "rows": [{"count": 2}], "row_count": 1}],
        llm_client=client,
        answer_intent="COUNT",
    )

    assert result["unsupported_claim_count"] >= 1
    assert result["fallback_used"] is True
    assert "2" in result["answer"]


def test_pure_llm_reports_are_shadow_only_and_packaged_default_unchanged(tiny_project):
    from scripts.run_pure_llm_tool_agent_eval import run_pure_llm_tool_agent_eval
    from scripts.run_pure_llm_promotion_gate import run_pure_llm_promotion_gate

    payload = run_pure_llm_tool_agent_eval(tiny_project, execute_real=False)
    gate = run_pure_llm_promotion_gate(tiny_project)

    assert payload["promotion_allowed"] is False
    assert gate["promotion_allowed"] is False
    assert gate["packaged_default_strategy"] == "SQL_FIRST_API_VERIFY"
    assert (tiny_project.outputs_dir / "reports" / "pure_llm_tool_agent_eval.json").exists()
