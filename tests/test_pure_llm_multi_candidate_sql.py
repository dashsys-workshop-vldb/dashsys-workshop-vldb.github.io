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
    return db, schema, context


def _published_timestamp_plan(candidate_id: str, *, column: str = "lastdeployedtime") -> dict:
    return {
        "candidate_id": candidate_id,
        "answer_intent": "DATE",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": [column],
        "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Welcome Journey"}],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
        "order_by": [],
        "limit": 50,
        "reason": "timestamp candidate",
        "confidence": 0.6,
    }


def test_candidate_ranker_prefers_published_timestamp_over_other_columns(tiny_project):
    from dashagent.llm_sql_candidate_ranker import rank_sql_plan_candidates

    db, schema, context = _context(tiny_project, "When was the journey 'Welcome Journey' published?")
    candidates = [
        _published_timestamp_plan("status_column", column="status"),
        _published_timestamp_plan("published_column", column="lastdeployedtime"),
    ]

    ranked = rank_sql_plan_candidates(
        "When was the journey 'Welcome Journey' published?",
        "DATE",
        context,
        candidates,
        schema,
        SQLValidator(schema),
        db=db,
        execution_probe=True,
    )

    assert ranked["selected_candidate_id"] == "published_column"
    assert ranked["ranking"][0]["candidate_id"] == "published_column"
    assert ranked["ranking"][0]["probe"]["probe_ok"] is True
    db.close()


def test_candidate_ranker_rejects_wrong_primary_table_and_selects_next_candidate(tiny_project):
    from dashagent.llm_sql_candidate_ranker import rank_sql_plan_candidates

    db, schema, context = _context(tiny_project, "List all journeys")
    wrong_table = {
        "candidate_id": "wrong_table",
        "answer_intent": "LIST",
        "primary_table": "dim_segment",
        "tables_needed": ["dim_segment"],
        "columns_needed": ["segment_id", "name"],
        "filters": [],
        "aggregation": {"type": "none", "table": "dim_segment", "column": ""},
        "limit": 50,
    }
    right_table = {
        "candidate_id": "right_table",
        "answer_intent": "LIST",
        "primary_table": "dim_campaign",
        "tables_needed": ["dim_campaign"],
        "columns_needed": ["campaign_id", "name"],
        "filters": [],
        "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
        "limit": 50,
    }

    ranked = rank_sql_plan_candidates(
        "List all journeys",
        "LIST",
        context,
        [wrong_table, right_table],
        schema,
        SQLValidator(schema),
        db=db,
        execution_probe=True,
    )

    assert ranked["selected_candidate_id"] == "right_table"
    assert "wrong_table" in ranked["rejection_reasons"]
    assert any("dim_campaign" in reason for reason in ranked["rejection_reasons"]["wrong_table"])
    db.close()


def test_multi_candidate_repair_loop_executes_best_candidate_with_probe(tiny_project):
    from dashagent.llm_sql_repair_loop import run_sql_repair_loop

    db, schema, context = _context(tiny_project, "When was the journey 'Welcome Journey' published?")
    client = FakeJsonClient(
        [
            json.dumps(
                {
                    "candidates": [
                        _published_timestamp_plan("bad_semantic", column="status"),
                        _published_timestamp_plan("good_semantic", column="lastdeployedtime"),
                    ]
                }
            )
        ]
    )

    result = run_sql_repair_loop(
        "When was the journey 'Welcome Journey' published?",
        context,
        db,
        SQLValidator(schema),
        llm_client=client,
        structured_sql_plan=True,
        semantic_verify=True,
        multi_candidate_sql_plan=True,
        execution_probe=True,
    )

    assert result["ok"] is True
    assert result["selected_candidate_id"] == "good_semantic"
    assert result["execution_success"] is True
    assert result["execution_result"]["rows"][0]["lastdeployedtime"] == "2026-01-01"
    db.close()


def test_sql_execution_evidence_bridge_extracts_key_fields():
    from dashagent.llm_sql_execution_evidence_bridge import build_sql_execution_evidence

    evidence = build_sql_execution_evidence(
        'SELECT "campaign_id", "name", "lastdeployedtime" FROM "dim_campaign"',
        {"ok": True, "row_count": 1, "rows": [{"campaign_id": "c2", "name": "Welcome Journey", "lastdeployedtime": "2026-01-01"}]},
    )

    assert evidence["sql_executed"] is True
    assert evidence["row_count"] == 1
    assert evidence["columns"] == ["campaign_id", "name", "lastdeployedtime"]
    assert evidence["key_ids"] == ["c2"]
    assert evidence["key_names"] == ["Welcome Journey"]
    assert evidence["timestamp_values"] == ["2026-01-01"]


def test_sql_execution_evidence_bridge_omits_sensitive_context_fields():
    from dashagent.llm_sql_execution_evidence_bridge import build_sql_execution_evidence

    evidence = build_sql_execution_evidence(
        'SELECT "campaign_id", "imsorgid" FROM "dim_campaign"',
        {"ok": True, "row_count": 1, "rows": [{"campaign_id": "c2", "imsorgid": "redacted-org-context"}]},
    )

    assert "imsorgid" not in evidence["columns"]
    assert "redacted-org-context" not in json.dumps(evidence).lower()
    assert evidence["key_ids"] == ["c2"]


def test_sql_result_answer_grounder_uses_sql_evidence_object():
    from dashagent.llm_sql_result_answer_grounder import ground_sql_result_answer

    evidence = {
        "sql_executed": True,
        "row_count": 1,
        "rows_preview": [{"campaign_id": "c2", "name": "Welcome Journey", "lastdeployedtime": "2026-01-01"}],
        "columns": ["campaign_id", "name", "lastdeployedtime"],
        "timestamp_values": ["2026-01-01"],
        "key_names": ["Welcome Journey"],
        "zero_rows": False,
    }

    result = ground_sql_result_answer(
        "When was the journey 'Welcome Journey' published?",
        "The available tool evidence does not contain enough supported data to answer.",
        {"ok": True, "rows": evidence["rows_preview"], "row_count": 1},
        answer_intent="DATE",
        sql_evidence=evidence,
    )

    assert result["sql_evidence_object_available"] is True
    assert result["sql_evidence_used_in_answer"] is True
    assert result["fallback_to_sql_evidence_answer"] is True
    assert "2026-01-01" in result["answer"]
    assert result["unsupported_claim_count"] == 0


def test_sql_result_answer_grounder_supports_iso_timestamp_subclaims():
    from dashagent.llm_sql_result_answer_grounder import ground_sql_result_answer

    evidence = {
        "sql_executed": True,
        "row_count": 1,
        "rows_preview": [{"campaign_id": "c2", "updatedtime": "2026-03-31T06:07:32.838462639Z"}],
        "columns": ["campaign_id", "updatedtime"],
        "timestamp_values": ["2026-03-31T06:07:32.838462639Z"],
        "zero_rows": False,
    }

    result = ground_sql_result_answer(
        "List journeys with timestamps",
        "No answer.",
        {"ok": True, "rows": evidence["rows_preview"], "row_count": 1},
        answer_intent="LIST",
        sql_evidence=evidence,
    )

    assert "06:07:32" in result["answer"]
    assert result["unsupported_claim_count"] == 0


def test_multi_candidate_variants_are_shadow_only(tiny_project):
    from dashagent.pure_llm_tool_agent import (
        CONSERVATIVE_SQL_FIRST_MULTI_CANDIDATE_V1,
        MULTI_CANDIDATE_SQL_GROUNDED_ANSWER_V1,
        MULTI_CANDIDATE_SQL_PLAN_V1,
        MULTI_CANDIDATE_SQL_PLAN_WITH_PROBE_V1,
        PURE_LLM_TOOL_AGENT_VARIANTS,
        pure_llm_baseline_definitions,
    )

    for variant in (
        MULTI_CANDIDATE_SQL_PLAN_V1,
        MULTI_CANDIDATE_SQL_PLAN_WITH_PROBE_V1,
        MULTI_CANDIDATE_SQL_GROUNDED_ANSWER_V1,
        CONSERVATIVE_SQL_FIRST_MULTI_CANDIDATE_V1,
    ):
        assert variant in PURE_LLM_TOOL_AGENT_VARIANTS
        definition = next(item for item in pure_llm_baseline_definitions() if item["variant"] == variant)
        assert definition["status"] == "shadow_diagnostic"
