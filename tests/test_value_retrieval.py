from __future__ import annotations

from dashagent.db import DuckDBDatabase
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.schema_index import SchemaIndex
from dashagent.value_retrieval import (
    build_value_index,
    extract_query_values,
    retrieve_value_matches,
    value_retrieval_summary,
)


def test_quoted_journey_name_retrieves_matching_value(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    tokens = extract_query_tokens("When was journey 'Birthday Message' published?", normalize_query("When was journey 'Birthday Message' published?"))
    mentions = extract_query_values(tokens.original, tokens)
    index = build_value_index(db, schema, tiny_project.outputs_dir / "cache", candidate_tables=["dim_campaign"])
    matches = retrieve_value_matches(mentions, index)

    assert any(match.matched_table == "dim_campaign" and match.matched_value == "Birthday Message" for match in matches)
    assert any(match.used_for == "sql_filter" for match in matches)


def test_batch_id_value_extraction_can_ground_api_param(tiny_project):
    tokens = extract_query_tokens("Show files for batch 69de8a0e0cc6102b5d11f01e")
    mentions = extract_query_values(tokens.original, tokens)

    assert any(mention.kind in {"batch_id", "id"} and mention.text == "69de8a0e0cc6102b5d11f01e" for mention in mentions)


def test_fuzzy_match_requires_high_threshold(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    tokens = extract_query_tokens("Find 'Birthday Mesage'")
    mentions = extract_query_values(tokens.original, tokens)
    index = build_value_index(db, schema, tiny_project.outputs_dir / "cache", candidate_tables=["dim_campaign"])
    matches = retrieve_value_matches(mentions, index)

    assert any(match.match_type == "fuzzy" and match.confidence >= 0.92 for match in matches)


def test_value_index_cache_and_budget_reporting(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    cache_dir = tiny_project.outputs_dir / "cache"
    first = build_value_index(db, schema, cache_dir, candidate_tables=["dim_campaign"], max_columns=1)
    second = build_value_index(db, schema, cache_dir, candidate_tables=["dim_campaign"], max_columns=1)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["scanned_columns"] <= 1


def test_value_retrieval_budget_exceeded_is_recorded(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    index = build_value_index(db, schema, tiny_project.outputs_dir / "cache_budget", candidate_tables=["dim_campaign"], max_ms=0)
    summary = value_retrieval_summary([], index, [])

    assert summary["value_retrieval_budget_exceeded"] is True
