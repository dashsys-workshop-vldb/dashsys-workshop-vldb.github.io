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

    assert result["unsupported_claim_count"] == 0
    assert result["rejected_unsupported_claim_count"] >= 1
    assert result["fallback_used"] is True
    assert "2" in result["answer"]


def test_evidence_locked_answer_supports_time_component_inside_evidence_timestamp(tiny_project):
    from dashagent.llm_evidence_locked_answer import evidence_locked_answer

    timestamp = "2026-03-31T06:07:32.838462639Z"
    client = FakeJsonClient([json.dumps({"answer": f"The timestamp is {timestamp}.", "claims": []})])

    result = evidence_locked_answer(
        "When was the journey published?",
        [{"source": "sql", "rows": [{"updatedtime": timestamp}], "row_count": 1}],
        llm_client=client,
        answer_intent="DATE",
    )

    assert result["unsupported_claim_count"] == 0


def test_pure_llm_agent_forces_tool_for_data_question(tiny_project):
    from dashagent.pure_llm_tool_agent import FULL_PURE_LLM_TOOL_AGENT_V1, run_pure_llm_tool_agent_variant

    db, schema = _schema(tiny_project)
    client = FakeJsonClient(
        [
            json.dumps({"answer_intent": "COUNT", "needs_sql": False, "needs_api": False}),
            json.dumps({"sql": "SELECT COUNT(*) AS count FROM dim_campaign", "tables_used": ["dim_campaign"]}),
            json.dumps({"answer": "There are 2 campaigns.", "claims": []}),
        ]
    )

    result = run_pure_llm_tool_agent_variant(
        "How many campaigns are there?",
        variant=FULL_PURE_LLM_TOOL_AGENT_V1,
        db=db,
        schema_index=schema,
        endpoint_catalog=EndpointCatalog(tiny_project),
        llm_client=client,
    )

    assert result["trace_assertions"]["did_llm_plan"] is True
    assert result["trace_assertions"]["did_llm_choose_tool"] is True
    assert result["trace_assertions"]["selected_tool"] == "execute_sql"
    assert result["trace_assertions"]["sql_validation_ok"] is True
    assert result["trace_assertions"]["tool_execution_ok"] is True
    db.close()


def test_pure_llm_agent_retries_bad_api_endpoint_choice(tiny_project):
    from dashagent.pure_llm_tool_agent import FULL_PURE_LLM_TOOL_AGENT_V1, run_pure_llm_tool_agent_variant

    db, schema = _schema(tiny_project)
    client = FakeJsonClient(
        [
            json.dumps({"answer_intent": "LIST", "needs_sql": False, "needs_api": True, "candidate_endpoints": ["ups_audiences"]}),
            json.dumps({"endpoint_id": "not_in_catalog", "method": "GET", "params": {"limit": 5}}),
            json.dumps({"endpoint_id": "ups_audiences", "method": "GET", "params": {"limit": 5}}),
            json.dumps({"answer": "The API evidence is unavailable.", "claims": []}),
        ]
    )

    result = run_pure_llm_tool_agent_variant(
        "List audience records from the UPS audiences endpoint.",
        variant=FULL_PURE_LLM_TOOL_AGENT_V1,
        db=db,
        schema_index=schema,
        endpoint_catalog=EndpointCatalog(tiny_project),
        api_client=None,
        llm_client=client,
    )

    assert result["trace_assertions"]["api_endpoint_candidate"] == "ups_audiences"
    assert result["trace_assertions"]["api_endpoint_validation_ok"] is True
    assert result["trace_assertions"]["api_endpoint_repair_attempted"] is True
    assert result["failure_stage"] == "tool_execution_failed"
    db.close()


def _count_plan(table: str = "dim_campaign", column: str = "campaign_id") -> dict:
    return {
        "answer_intent": "COUNT",
        "primary_entity": "campaign",
        "primary_table": table,
        "tables_needed": [table],
        "columns_needed": [column],
        "join_needed": False,
        "join_path_reason": "",
        "filters": [],
        "aggregation": {"type": "count", "table": table, "column": column},
        "order_by": [],
        "limit": 50,
        "confidence": 0.8,
    }


def test_structured_sql_plan_rejects_unknown_business_term_table(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_plan_compiler import validate_structured_sql_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("List journeys.", schema, EndpointCatalog(tiny_project))
    bad_plan = _count_plan(table="journey", column="id")

    result = validate_structured_sql_plan(bad_plan, schema, context)

    assert result["ok"] is False
    assert any("Unknown table: journey" in error for error in result["errors"])
    assert result["alias_suggestions"]["journey"] == "dim_campaign"
    db.close()


def test_structured_sql_plan_compiler_counts_and_rejects_unknown_columns(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_plan_compiler import compile_structured_sql_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many journeys?", schema, EndpointCatalog(tiny_project))
    compiled = compile_structured_sql_plan(_count_plan(), schema, context)
    bad = compile_structured_sql_plan(_count_plan(column="journey_name"), schema, context)

    assert compiled["ok"] is True
    assert compiled["sql"] == 'SELECT COUNT("campaign_id") AS count FROM "dim_campaign"'
    assert SQLValidator(schema).validate(compiled["sql"]).ok is True
    assert bad["ok"] is False
    assert any("Unknown column" in error for error in bad["errors"])
    db.close()


def test_structured_sql_plan_compiler_accepts_llm_shaped_safe_plan(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_plan_compiler import compile_structured_sql_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many journeys?", schema, EndpointCatalog(tiny_project))
    plan = {
        "answer_intent": "COUNT",
        "primary_entity": "journeys",
        "primary_table": "dim_campaign",
        "tables_needed": [{"table_name": "dim_campaign"}],
        "columns_needed": [{"column_name": "COUNT(*)"}],
        "aggregation": [{"function": "COUNT", "columns": ["*"]}],
        "filters": [],
    }

    compiled = compile_structured_sql_plan(plan, schema, context)

    assert compiled["ok"] is True
    assert compiled["sql"] == 'SELECT COUNT(*) AS count FROM "dim_campaign"'
    assert SQLValidator(schema).validate(compiled["sql"]).ok is True
    db.close()


def test_structured_sql_plan_compiler_selects_with_safe_filter_and_limit(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_plan_compiler import compile_structured_sql_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("List published journeys.", schema, EndpointCatalog(tiny_project))
    plan = {
        **_count_plan(),
        "answer_intent": "LIST",
        "columns_needed": ["name", "status"],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
        "filters": [{"table": "dim_campaign", "column": "status", "operator": "equals", "value_source": "status_term", "value": "published"}],
        "limit": 25,
    }

    compiled = compile_structured_sql_plan(plan, schema, context)

    assert compiled["ok"] is True
    assert 'SELECT "name", "status" FROM "dim_campaign"' in compiled["sql"]
    assert 'WHERE "dim_campaign"."status" = ' in compiled["sql"]
    assert compiled["sql"].endswith("LIMIT 25")
    assert SQLValidator(schema).validate(compiled["sql"]).ok is True
    db.close()


def test_structured_sql_plan_compiler_normalizes_safe_llm_aliases(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_plan_compiler import compile_structured_sql_plan

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("When was the campaign named Birthday Message updated?", schema, EndpointCatalog(tiny_project))
    plan = {
        **_count_plan(),
        "answer_intent": "DATE",
        "columns_needed": ["name"],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
        "filters": [{"table": "dim_campaign", "column": "campaign_name", "operator": "=", "value": "Birthday Message"}],
        "limit": 1,
    }

    compiled = compile_structured_sql_plan(plan, schema, context)

    assert compiled["ok"] is True
    assert '"name" = ' in compiled["sql"]
    assert SQLValidator(schema).validate(compiled["sql"]).ok is True
    db.close()


def test_structured_sql_repair_loop_unwraps_nested_repair_plan(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("List campaigns.", schema, EndpointCatalog(tiny_project))
    wrapped_plan = {
        "primary_plan": {
            "answer_intent": "LIST",
            "primary_entity": "campaign",
            "primary_table": "dim_campaign",
            "tables_needed": ["dim_campaign"],
            "columns_needed": ["campaign_id", "name"],
            "join_needed": False,
            "join_path_reason": "",
            "filters": [],
            "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
            "order_by": [],
            "limit": 50,
            "confidence": 0.8,
        }
    }
    client = FakeJsonClient([json.dumps(wrapped_plan)])

    result = run_sql_repair_loop(
        "List campaigns.",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        max_repair_rounds=2,
        structured_sql_plan=True,
    )

    assert result["ok"] is True
    assert result["repair_rounds"] == 0
    assert "dim_campaign" in result["sql"]
    db.close()


def test_structured_sql_plan_repair_loop_compiles_repaired_plan(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many journeys?", schema, EndpointCatalog(tiny_project))
    client = FakeJsonClient(
        [
            json.dumps(_count_plan(table="journeys", column="id")),
            json.dumps(_count_plan(table="dim_campaign", column="campaign_id")),
        ]
    )

    result = run_sql_repair_loop(
        "How many journeys?",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        max_repair_rounds=2,
        structured_sql_plan=True,
    )

    assert result["ok"] is True
    assert result["plan_validation_success"] is True
    assert result["compile_success"] is True
    assert result["sql_validation_success"] is True
    assert result["repair_rounds"] == 1
    assert result["attempts"][0]["executed"] is False
    assert result["sql"] == 'SELECT COUNT("campaign_id") AS count FROM "dim_campaign"'
    db.close()


def test_structured_sql_plan_unrepairable_returns_safe_failure(tiny_project):
    from dashagent.llm_sql_context_builder import build_llm_sql_context
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema = _schema(tiny_project)
    context = build_llm_sql_context("How many journeys?", schema, EndpointCatalog(tiny_project))
    client = FakeJsonClient([json.dumps(_count_plan(table="journeys", column="id"))] * 3)

    result = run_sql_repair_loop(
        "How many journeys?",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        max_repair_rounds=2,
        structured_sql_plan=True,
    )

    assert result["ok"] is False
    assert result["failure_stage"] == "sql_plan_unrepairable"
    assert "could not produce a validated SQL query" in result["safe_answer"]
    assert all(attempt["executed"] is False for attempt in result["attempts"])
    db.close()


def test_stabilization_set_and_report_are_diagnostic_only(tiny_project):
    from scripts.run_pure_llm_tool_agent_eval import run_pure_llm_tool_agent_eval

    stabilization_path = Path("data/pure_llm_stabilization_set.json")
    assert stabilization_path.exists()
    items = json.loads(stabilization_path.read_text())
    assert 8 <= len(items) <= 10
    assert {item["category"] for item in items} >= {"sql_count", "api_only_audience", "sql_api_verification"}

    payload = run_pure_llm_tool_agent_eval(tiny_project, execute_real=False, stabilization_set=True)

    assert payload["stabilization_set"] is True
    assert payload["promotion_allowed"] is False
    assert (tiny_project.outputs_dir / "reports" / "pure_llm_tool_agent_stabilization.json").exists()


def test_pure_llm_reports_are_shadow_only_and_packaged_default_unchanged(tiny_project):
    from scripts.run_pure_llm_tool_agent_eval import run_pure_llm_tool_agent_eval
    from scripts.run_pure_llm_promotion_gate import run_pure_llm_promotion_gate

    payload = run_pure_llm_tool_agent_eval(tiny_project, execute_real=False)
    gate = run_pure_llm_promotion_gate(tiny_project)

    assert payload["promotion_allowed"] is False
    assert gate["promotion_allowed"] is False
    assert gate["packaged_default_strategy"] == "SQL_FIRST_API_VERIFY"
    assert (tiny_project.outputs_dir / "reports" / "pure_llm_tool_agent_eval.json").exists()
