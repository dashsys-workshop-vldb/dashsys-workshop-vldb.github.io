from __future__ import annotations

from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.endpoint_family_ranker import detect_endpoint_family, rank_endpoint_candidates
from dashagent.query_tokens import extract_query_tokens


def _family(query: str) -> str | None:
    return detect_endpoint_family(extract_query_tokens(query)).family


def test_hidden_style_batch_file_paraphrases_are_stable(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    queries = [
        "Show downloadable assets for export batch 69de8a0e0cc6102b5d11f01e",
        "Retrieve file inventory for batch 69de8a0e0cc6102b5d11f01e",
    ]
    for query in queries:
        ranked = rank_endpoint_candidates(extract_query_tokens(query), catalog.endpoints)
        assert ranked["detected_family"]["endpoint_family"] == "batch_files"
        assert ranked["ranked_endpoints"][0]["id"] == "export_batch_files"


def test_hidden_style_failed_batch_file_paraphrases_are_stable(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    query = "For batch 69de8a0e0cc6102b5d11f01e, list the failed file outputs"
    ranked = rank_endpoint_candidates(extract_query_tokens(query), catalog.endpoints)
    assert ranked["detected_family"]["endpoint_family"] == "batch_failed_files"
    assert ranked["ranked_endpoints"][0]["id"] == "export_batch_failed"


def test_hidden_style_tag_schema_segment_and_journey_families(tiny_project):
    assert _family("Count available governance tags") == "tag_list"
    assert _family("Open the tag named Loyal Customers") in {"tag_detail", "tag_list"}
    assert _family("Show details for schema named Customer Profile") in {"schema_detail", "schema_list"}
    assert _family("Find datasets associated with schema Customer Profile") in {"schema_detail", "dataset_list"}
    assert _family("List recent audience evaluation jobs") == "segment_jobs"
    assert _family("Show active journey records") == "journey_list"


def test_repair_execution_flags_default_disabled(tiny_project):
    config = Config.from_env(tiny_project.project_root)
    assert config.enable_gated_risk_cluster_repair_execution is False
    assert config.enable_repair_for_batch_endpoint_confusion is False
    assert config.enable_repair_for_tag_api_confusion is False
    assert config.enable_repair_for_schema_dataset_confusion is False
    assert config.enable_repair_for_zero_score_margin is False
    assert config.enable_repair_for_missing_api_topk is False
