from __future__ import annotations

from dashagent.raw_sql_safety_gate import RawSQLSafetyGate


def test_select_with_limit_and_count_without_limit_pass():
    gate = RawSQLSafetyGate(max_sql_length=500)

    assert gate.check("SELECT name FROM dim_campaign LIMIT 10", []).passed is True
    assert gate.check("SELECT COUNT(*) AS count FROM dim_campaign", []).passed is True


def test_mutations_ddl_pragma_and_multiple_statements_fail():
    gate = RawSQLSafetyGate()

    assert gate.check("UPDATE dim_campaign SET status = 'x'", []).error_type == "non_select"
    assert gate.check("DROP TABLE dim_campaign", []).error_type == "non_select"
    assert gate.check("PRAGMA show_tables", []).error_type == "non_select"
    assert gate.check("SELECT 1; SELECT 2", []).error_type == "multiple_statements"


def test_select_without_limit_fails_unless_aggregate():
    gate = RawSQLSafetyGate()

    result = gate.check("SELECT name FROM dim_campaign", [])

    assert result.passed is False
    assert result.error_type == "missing_limit"


def test_comments_invalid_params_and_long_sql_fail():
    gate = RawSQLSafetyGate(max_sql_length=40)

    assert gate.check("SELECT name FROM dim_campaign -- comment\nLIMIT 10", []).error_type == "forbidden_keyword"
    assert gate.check("SELECT name FROM dim_campaign LIMIT 10", {"x": 1}).error_type == "invalid_params"
    assert gate.check("SELECT name, status, published_at FROM dim_campaign WHERE name = ? LIMIT 10", ["Birthday Message"]).error_type == "sql_too_long"
