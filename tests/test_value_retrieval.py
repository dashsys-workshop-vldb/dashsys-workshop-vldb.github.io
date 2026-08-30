from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dashagent.db import DuckDBDatabase
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.schema_index import SchemaIndex
from dashagent.value_retrieval import (
    _VALUE_INDEX_L1,
    build_value_index,
    extract_query_values,
    retrieve_value_matches,
    stable_cache_key,
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
    assert first["cache_key_algorithm"] == "sha256"
    assert first["cache_reproducible"] is True
    assert first["budget"] == second["budget"]


def test_value_retrieval_budget_exceeded_is_recorded(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    index = build_value_index(db, schema, tiny_project.outputs_dir / "cache_budget", candidate_tables=["dim_campaign"], max_ms=0)
    summary = value_retrieval_summary([], index, [])

    assert summary["value_retrieval_budget_exceeded"] is True


def test_stable_cache_key_is_reproducible_across_calls_and_processes():
    key = "dim_campaign|6|18|500|250"
    expected = stable_cache_key(key)
    assert expected == stable_cache_key(key)
    assert expected != stable_cache_key(key + "|different")

    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from dashagent.value_retrieval import stable_cache_key; print(stable_cache_key('dim_campaign|6|18|500|250'))",
        ],
        text=True,
    ).strip()
    assert output == expected


def test_stable_cache_file_reused_from_disk(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    cache_dir = tiny_project.outputs_dir / "cache_disk"
    _VALUE_INDEX_L1.clear()
    first = build_value_index(db, schema, cache_dir, candidate_tables=["dim_campaign"], max_columns=1)
    first_path = first["cache_path"]
    _VALUE_INDEX_L1.clear()
    second = build_value_index(db, schema, cache_dir, candidate_tables=["dim_campaign"], max_columns=1)

    assert second["cache_hit"] is True
    assert Path(second["cache_path"]).name == Path(first_path).name
    assert second["warm_cache_lookup_ms"] is not None
    payload = json.loads((cache_dir / first_path.split("/")[-1]).read_text(encoding="utf-8"))
    assert payload["cache_key_algorithm"] == "sha256"
    assert "secret" not in json.dumps(payload).lower()


def test_value_retrieval_cache_filename_does_not_use_python_hash():
    source = (Path(__file__).resolve().parents[1] / "dashagent" / "value_retrieval.py").read_text(encoding="utf-8")
    assert "abs(hash(" not in source
    assert "hash(key)" not in source
