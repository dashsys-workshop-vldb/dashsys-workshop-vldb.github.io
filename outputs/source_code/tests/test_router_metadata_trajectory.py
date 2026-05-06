from __future__ import annotations

import json

from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.metadata_selector import MetadataSelector
from dashagent.router import QueryRouter
from dashagent.schema_index import SchemaIndex
from dashagent.trajectory import TrajectoryLogger


def test_router_classifies_journey_status_query(tiny_project):
    db = DuckDBDatabase(tiny_project)
    router = QueryRouter(db.list_tables(), EndpointCatalog(tiny_project))
    decision = router.route("Is the Birthday Message journey published?")
    assert decision.domain_type == "JOURNEY_CAMPAIGN"
    assert decision.route_type == "SQL_THEN_API"
    assert "dim_campaign" in decision.candidate_tables


def test_metadata_selector_returns_compact_context(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(tiny_project)
    router = QueryRouter(db.list_tables(), catalog)
    decision = router.route("How many segments are there?")
    metadata = MetadataSelector(schema, catalog, tiny_project).select(
        "How many segments are there?",
        decision,
        strategy="SQL_ONLY_BASELINE",
        query_id="q1",
    )
    assert metadata["selected_tables"]
    assert "selected_columns" in metadata
    assert len(metadata["selected_join_hints"]) <= tiny_project.max_join_hints
    assert len(metadata["known_example_patterns"]) <= tiny_project.max_gold_patterns
    assert len(json.dumps(metadata)) < 12000


def test_trajectory_redacts_secrets(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN", "secret-token-value-12345")
    logger = TrajectoryLogger("q1", "query", "strategy", "SQL_ONLY", "UNKNOWN")
    logger.add_api_call(
        "GET",
        "/ajo/journey",
        {},
        {"Authorization": "Bearer secret-token-value-12345", "x-api-key": "abc"},
        {"ok": True},
        {"ok": True, "echo": "secret-token-value-12345"},
    )
    payload = logger.finish("done")
    text = json.dumps(payload)
    assert "secret-token-value-12345" not in text
    assert "[REDACTED]" in text
