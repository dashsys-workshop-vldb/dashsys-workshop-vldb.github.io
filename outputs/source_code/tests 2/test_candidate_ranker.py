from __future__ import annotations

from dashagent.candidate_ranker import rank_candidates, reciprocal_rank_fusion, score_candidate
from dashagent.endpoint_family_ranker import ENDPOINT_FAMILY_RULE_SOURCES, detect_endpoint_family, rank_endpoint_candidates
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.query_tokens import extract_query_tokens


def test_hybrid_score_components_are_deterministic():
    tokens = extract_query_tokens("List all journeys")
    candidate = {"name": "dim_campaign", "kind": "table", "base_score": 0.5, "aliases": ["journey"]}
    first = score_candidate(tokens, candidate, schema_links={"links": [{"table": "dim_campaign", "score": 1.0}]})
    second = score_candidate(tokens, candidate, schema_links={"links": [{"table": "dim_campaign", "score": 1.0}]})

    assert first == second
    assert first["lexical_score"] >= 0
    assert first["alias_score"] > 0
    assert first["final_score"] > first["base_score"]
    assert "lexical=" in first["score_explanation"]


def test_reciprocal_rank_fusion_reduces_ties_from_different_rankings():
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "a"], ["b", "c"]])
    assert scores["b"] > scores["a"]
    ranked = rank_candidates(
        extract_query_tokens("journey status"),
        [
            {"name": "dim_campaign", "kind": "table", "base_score": 0.5, "aliases": ["journey"]},
            {"name": "dim_segment", "kind": "table", "base_score": 0.5, "aliases": []},
        ],
        fusion_mode="reciprocal_rank_fusion",
    )
    assert ranked["ranked_candidates"][0]["name"] == "dim_campaign"


def test_endpoint_family_rules_are_domain_sourced():
    assert ENDPOINT_FAMILY_RULE_SOURCES
    forbidden = "public example"
    assert all(forbidden not in source.lower() for source in ENDPOINT_FAMILY_RULE_SOURCES.values())


def test_batch_id_files_boosts_batch_files_endpoint(tiny_project):
    tokens = extract_query_tokens("Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?")
    catalog = EndpointCatalog(tiny_project)
    ranked = rank_endpoint_candidates(tokens, catalog.endpoints)
    assert ranked["detected_family"]["endpoint_family"] == "batch_files"
    assert ranked["ranked_endpoints"][0]["id"] == "export_batch_files"


def test_failed_files_boosts_failed_batch_endpoint(tiny_project):
    tokens = extract_query_tokens("Which failed files are in batch 69de8a0e0cc6102b5d11f01e?")
    catalog = EndpointCatalog(tiny_project)
    ranked = rank_endpoint_candidates(tokens, catalog.endpoints)
    assert ranked["detected_family"]["endpoint_family"] == "batch_failed_files"
    assert ranked["ranked_endpoints"][0]["id"] == "export_batch_failed"


def test_tag_and_schema_dataset_family_separation(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    tag_ranked = rank_endpoint_candidates(extract_query_tokens("How many tags do I have?"), catalog.endpoints)
    assert tag_ranked["detected_family"]["endpoint_family"] == "tag_list"
    assert tag_ranked["ranked_endpoints"][0]["id"] == "unified_tags"

    schema_ranked = rank_endpoint_candidates(extract_query_tokens("Which datasets use schema 'Customer Actions'?"), catalog.endpoints)
    assert schema_ranked["detected_family"]["endpoint_family"] in {"schema_detail", "dataset_list"}
    assert schema_ranked["ranked_endpoints"][0]["id"] in {"schema_registry_schema", "catalog_datasets"}


def test_value_match_confidence_gate_for_api_ranking():
    tokens = extract_query_tokens("Show tag named Loyal")
    low = detect_endpoint_family(tokens, [{"kind": "tag", "matched_column": "name", "confidence": 0.9, "used_for": "api_param"}])
    high = detect_endpoint_family(tokens, [{"kind": "tag", "matched_column": "name", "confidence": 0.95, "used_for": "api_param"}])
    assert low.value_match_used_for_api_ranking is False
    assert high.value_match_used_for_api_ranking is True
