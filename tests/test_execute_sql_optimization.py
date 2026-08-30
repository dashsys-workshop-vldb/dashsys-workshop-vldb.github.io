from __future__ import annotations

from dashagent.core_tool_policy import compact_sql_result_for_intent
from dashagent.db import DuckDBDatabase
from dashagent.schema_index import SchemaIndex
from dashagent.validators import SQLValidator


def test_sql_validator_exact_cache_keeps_read_only_guard(tiny_project):
    schema = SchemaIndex.build(DuckDBDatabase(tiny_project))
    validator = SQLValidator(schema)

    first = validator.validate("SELECT COUNT(*) AS count FROM dim_campaign")
    second = validator.validate(" SELECT COUNT(*) AS count FROM dim_campaign; ")
    unsafe = validator.validate("DELETE FROM dim_campaign")
    stats = validator.validation_cache_stats()

    assert first.ok is True
    assert second.ok is True
    assert unsafe.ok is False
    assert "blocked write" in unsafe.errors[0] or "read-only" in unsafe.errors[0]
    assert stats["entries"] >= 2
    assert stats["unsafe_cached_as_safe"] == 0
    assert stats["hits"] >= 1


def test_execute_sql_destructive_query_remains_blocked(tiny_project):
    db = DuckDBDatabase(tiny_project)
    result = db.execute_sql("DROP TABLE dim_campaign")

    assert result["ok"] is False
    assert result["rows"] == []
    assert result["row_count"] == 0


def test_count_intent_sql_result_compacts_without_losing_count():
    payload = {
        "ok": True,
        "row_count": 1,
        "rows": [{"count": 2, "unused_name": "not-needed"}],
        "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
    }

    compact = compact_sql_result_for_intent("count", payload)

    assert compact["ok"] is True
    assert compact["row_count"] == 1
    assert compact["evidence_shape"] == "count"
    assert compact["key_fields"] == {"count": 2}
    assert compact["rows_preview"] == [{"count": 2}]


def test_list_intent_sql_result_preserves_names_and_ids():
    payload = {
        "ok": True,
        "row_count": 2,
        "rows": [
            {"segment_id": "s1", "name": "High Value", "profile_count": 12},
            {"segment_id": "s2", "name": "Recent Buyers", "profile_count": 8},
        ],
    }

    compact = compact_sql_result_for_intent("list", payload)

    assert compact["evidence_shape"] == "key_fields"
    assert compact["row_count"] == 2
    assert compact["rows_preview"] == [
        {"segment_id": "s1", "name": "High Value"},
        {"segment_id": "s2", "name": "Recent Buyers"},
    ]
