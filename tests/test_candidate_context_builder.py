from __future__ import annotations

from dashagent.candidate_context_builder import (
    build_candidate_context,
    build_full_schema_context,
    forward_schema_link,
    preserve_structural_relations,
    preserve_structural_joins,
)
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.executor import AgentExecutor


def test_candidate_context_is_retrieval_only(tiny_project):
    executor = AgentExecutor(tiny_project)
    context = build_candidate_context("List all journeys", executor.schema_index, EndpointCatalog(tiny_project))
    assert context["used_gold_patterns"] is False
    assert context["candidate_tables"]
    assert "candidate_columns" in context
    assert "candidate_join_hints" in context
    assert "candidate_apis" in context
    assert context["schema_linking"]["used_robust_schema_linking"] is True


def test_full_schema_context_contains_all_tables(tiny_project):
    executor = AgentExecutor(tiny_project)
    context = build_full_schema_context(executor.schema_index, EndpointCatalog(tiny_project))
    assert set(context["tables"]) == set(executor.schema_index.tables)


def test_schema_linking_maps_journey_to_campaign(tiny_project):
    executor = AgentExecutor(tiny_project)
    context = build_candidate_context("List all journeys", executor.schema_index, EndpointCatalog(tiny_project))
    linked_tables = {
        link["table"]
        for link in context["schema_linking"]["forward_links"]
        if link.get("query_term") in {"journey", "journeys"}
    }
    assert "dim_campaign" in linked_tables


def test_status_words_link_to_status_columns(tiny_project):
    executor = AgentExecutor(tiny_project)
    forward = forward_schema_link(type("T", (), {"words": ["published"], "statuses": ["published"], "domain_tokens": ["journey_campaign"]})(), executor.schema_index)
    assert any(link.get("column") == "status" for link in forward["links"])


def test_structural_join_preservation_keeps_bridge_tables(tiny_project):
    structural = preserve_structural_joins(
        ["dim_segment"],
        [{"left_table": "dim_segment", "right_table": "hkg_br_segment_target", "reason": "Segment to target bridge."}],
    )
    assert "hkg_br_segment_target" in structural["added_bridge_tables"]


def test_candidate_context_includes_ranking_diagnostics(tiny_project):
    executor = AgentExecutor(tiny_project)
    context = build_candidate_context("Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?", executor.schema_index, EndpointCatalog(tiny_project))
    assert context["hybrid_candidate_scoring"]["active"] is True
    assert context["endpoint_family_ranking"]["endpoint_family"] == "batch_files"
    assert context["candidate_apis"][0]["id"] == "export_batch_files"
    assert context["gated_risk_cluster_repair"]["diagnostic_only"] is True
    assert context["gated_risk_cluster_repair"]["execution_repair_enabled"] is False


def test_structural_relation_preservation_is_schema_level(tiny_project):
    executor = AgentExecutor(tiny_project)
    synthetic_tokens = type("T", (), {"words": ["segment", "destination"], "domain_tokens": ["segment_audience", "destination_dataflow"]})()
    structural = preserve_structural_relations(synthetic_tokens, ["dim_segment"], executor.schema_index)
    assert structural["added_tables"] == []
    assert isinstance(structural["rule_sources"], list)
