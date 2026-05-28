from __future__ import annotations

from dashagent.db import DuckDBDatabase
from dashagent.schema_index import SchemaIndex
from dashagent.sql_ast_tools import (
    detect_destructive_sql,
    detect_unknown_columns,
    detect_unknown_tables,
    extract_sql_columns,
    extract_sql_tables,
    normalize_sql_ast,
    sql_ast_summary,
)
from dashagent.span_exporter import checkpoints_to_spans
from dashagent.validators import SQLValidator


def test_valid_sql_parses_and_extracts_tables_columns(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    sql = 'SELECT "name", status FROM "dim_campaign" WHERE status = \'published\''

    assert extract_sql_tables(sql) == ["dim_campaign"]
    assert set(extract_sql_columns(sql)) >= {"name", "status"}
    assert "dim_campaign" in normalize_sql_ast(sql)
    assert sql_ast_summary(sql, schema)["parsed_ok"] is True


def test_destructive_sql_blocked(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    validator = SQLValidator(schema)

    assert detect_destructive_sql("DROP TABLE dim_campaign")
    result = validator.validate("DROP TABLE dim_campaign")
    assert not result.ok
    assert any("blocked" in error.lower() for error in result.errors)


def test_unknown_table_detected_with_semantic_suggestion(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    summary = sql_ast_summary("SELECT name FROM journey", schema)

    assert detect_unknown_tables("SELECT name FROM journey", set(schema.tables)) == ["journey"]
    assert "dim_campaign" in summary["closest_table_suggestions"]["journey"]


def test_unknown_column_detected(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))

    summary = sql_ast_summary("SELECT nmae FROM dim_campaign", schema)
    assert detect_unknown_columns("SELECT bogus FROM dim_campaign", schema) == ["bogus"]
    assert "name" in summary["closest_column_suggestions"]["nmae"]
    result = SQLValidator(schema).validate("SELECT bogus FROM dim_campaign")
    assert not result.ok
    assert any("Unknown column" in error for error in result.errors)


def test_quoted_identifiers_work(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    summary = sql_ast_summary('SELECT "name" FROM "dim_campaign"', schema)

    assert summary["parsed_ok"] is True
    assert summary["unknown_tables"] == []
    assert summary["unknown_columns"] == []


def test_invalid_sql_records_parse_error_without_crashing(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    summary = sql_ast_summary("SELECT * FROM", schema)

    assert summary["parsed_ok"] is False
    assert summary["parse_error"]


def test_span_export_marks_sql_ast_validation_span():
    spans = checkpoints_to_spans(
        {
            "query_id": "q",
            "strategy": "SQL_FIRST_API_VERIFY",
            "checkpoints": [
                {
                    "checkpoint_id": "checkpoint_sql_ast_validation",
                    "stage": "validation",
                    "technique": "SQLGlot AST-based SQL validation and extraction",
                    "output": {"parsed_ok": True},
                }
            ],
        }
    )

    assert spans["spans"][0]["span_kind"] == "sql_ast_validation_span"
