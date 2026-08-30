from __future__ import annotations

from dashagent.db import DuckDBDatabase
from dashagent.gated_sql_candidates import hard_case_triggers, select_gated_sql_candidate
from dashagent.planner import Plan, PlanStep
from dashagent.query_decomposer import decompose_query, should_decompose_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.schema_index import SchemaIndex
from dashagent.validators import SQLValidator


def test_simple_query_does_not_trigger_decomposition():
    tokens = extract_query_tokens("List all journeys")
    assert should_decompose_query("List all journeys", tokens) is False
    assert decompose_query("List all journeys", tokens)["active"] is False


def test_complex_query_triggers_decomposition():
    query = "List all segment audiences connected to destination 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime."
    tokens = extract_query_tokens(query)
    decomposition = decompose_query(query, tokens)

    assert decomposition["active"] is True
    assert decomposition["expected_answer_shape"] == "table_or_list"
    assert decomposition["sub_questions"]


def test_low_confidence_and_validation_failure_trigger_gated_candidates():
    reasons = hard_case_triggers(
        candidate_context={"confidence": 0.2, "score_margin": 0.0, "schema_linking": {"schema_link_risk": "high"}},
        validation_failed=True,
    )

    assert "high_schema_link_risk" in reasons
    assert "low_candidate_confidence" in reasons
    assert "zero_score_margin" in reasons
    assert "sql_validation_failed" in reasons


def test_gated_candidate_selection_validates_and_selects_one(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    validator = SQLValidator(schema)
    plan = Plan(
        strategy="SQL_FIRST_API_VERIFY",
        rationale="test",
        steps=[PlanStep(action="sql", purpose="test", sql="SELECT name FROM dim_campaign", family="test")],
    )
    result = select_gated_sql_candidate(
        query="List all journeys",
        plan=plan,
        sql_validator=validator,
        expected_answer_shape="table_or_list",
        trigger_reasons=["complex_query_decomposition"],
    )

    assert result["hard_case_triggered"] is True
    assert result["candidate_count"] == 1
    assert result["selected_candidate"]["validation_ok"] is True
    assert "losing candidates are not executed" in result["selection_policy"]


def test_gated_candidate_max_count_enforced(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    validator = SQLValidator(schema)
    steps = [
        PlanStep(action="sql", purpose=str(index), sql="SELECT name FROM dim_campaign", family="test")
        for index in range(5)
    ]
    result = select_gated_sql_candidate(
        query="complex",
        plan=Plan("SQL_FIRST_API_VERIFY", "test", steps),
        sql_validator=validator,
        trigger_reasons=["complex_query_decomposition"],
        max_candidates=3,
    )

    assert result["candidate_count"] == 3
