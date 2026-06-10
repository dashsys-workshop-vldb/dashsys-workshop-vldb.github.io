from scripts.run_weak_model_generated_prompt_diagnostic import classify_generated_failure
from scripts.run_weak_model_sql_bottleneck_analysis import classify_sql_bottleneck


def test_generated_diagnostic_flags_wrong_table_from_hints():
    row = {
        "unsupported_claims": 0,
        "validation_failure_count": 0,
        "sql_candidate": 'SELECT "id" FROM "dim_segment"',
        "selected_sql_table": "dim_segment",
        "evidence_need": "sql_primary_api_verify",
    }
    item = {"target_tables_hint": ["dim_campaign"], "expected_route_diagnostic": "SQL_PLUS_API"}
    assert classify_generated_failure(row, item) == "wrong_table"


def test_generated_diagnostic_flags_api_evidence_not_used_when_required():
    row = {
        "unsupported_claims": 0,
        "validation_failure_count": 0,
        "sql_candidate": 'SELECT "id" FROM "dim_campaign"',
        "selected_sql_table": "dim_campaign",
        "endpoint_selected": "journey_list",
        "api_validation_ok": True,
        "answer_used_api_evidence": False,
        "evidence_need": "sql_primary_api_verify",
    }
    item = {"target_tables_hint": ["dim_campaign"], "expected_route_diagnostic": "SQL_PLUS_API"}
    assert classify_generated_failure(row, item) == "api_evidence_not_used"


def test_sql_bottleneck_flags_missing_filter_for_quoted_entity():
    row = {
        "prompt": "When was the journey 'Birthday Message' published?",
        "semantic_slots": {"intent": "DATE", "domain": "JOURNEY"},
        "compiled_sql": 'SELECT "LASTDEPLOYEDTIME" FROM "dim_campaign"',
        "selected_table": "dim_campaign",
        "selected_columns": ["LASTDEPLOYEDTIME"],
        "filters": [],
        "sql_validation_ok": True,
        "sql_score": 0.0,
        "answer_used_sql_evidence": True,
    }
    assert classify_sql_bottleneck(row) == "missing_filter"


def test_sql_bottleneck_flags_answer_grounding_gap_for_good_sql():
    row = {
        "prompt": "List all journeys",
        "semantic_slots": {"intent": "LIST", "domain": "JOURNEY"},
        "compiled_sql": 'SELECT "ID", "NAME" FROM "dim_campaign"',
        "selected_table": "dim_campaign",
        "selected_columns": ["ID", "NAME"],
        "filters": [],
        "sql_validation_ok": True,
        "sql_score": 0.9,
        "answer_used_sql_evidence": False,
    }
    assert classify_sql_bottleneck(row) == "SQL_result_not_used"
