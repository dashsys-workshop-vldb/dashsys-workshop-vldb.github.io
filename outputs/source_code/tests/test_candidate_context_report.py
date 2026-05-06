from __future__ import annotations

from scripts.generate_candidate_context_report import generate_candidate_context_report, normalize_table_name, recall_at_k


def test_candidate_context_report_parseable(tiny_project):
    report = generate_candidate_context_report(tiny_project)
    assert report["examples"] >= 1
    assert report["used_gold_patterns"] is False
    assert "compression_ratio" in report["summary"]
    assert "context_mode_distribution" in report["summary"]
    assert "avg_forward_link_count" in report["summary"]
    assert "schema_link_risk_distribution" in report["summary"]
    assert "candidate_miss_analysis" in report
    assert "candidate_risk_clusters" in report
    assert "zero_score_margin" in report["candidate_risk_clusters"]
    assert "before_count" in report["candidate_risk_clusters"]["zero_score_margin"]
    assert "after_count" in report["candidate_risk_clusters"]["zero_score_margin"]
    assert "cluster_gate" in report
    assert report["candidate_risk_clusters"]["zero_score_margin"]["diagnostic_only"] is True
    assert report["candidate_risk_clusters"]["zero_score_margin"]["behavior_changing"] is False
    assert "schema_linking" in report["rows"][0]
    assert "hybrid_candidate_scoring" in report["rows"][0]
    assert "endpoint_family_ranking" in report["rows"][0]
    assert "ranking_diagnostics" in report["rows"][0]
    assert "risk_efficiency_controller" in report["rows"][0]
    assert "schema_context_vote" in report["rows"][0]
    assert "risk_level_distribution" in report["summary"]
    assert report["summary"]["estimated_savings_label"].startswith("estimated only")
    assert report["rows"][0]["savings_are_estimates"] is True
    assert report["rows"][0]["measured_efficiency_improvement_claimed"] is False
    assert report["curated_join_hint_audit"]["used_gold_patterns"] is False


def test_table_recall_normalizes_case_quotes_and_prefixes():
    assert recall_at_k(["dim_campaign"], {"DIM_CAMPAIGN"}, 3) == 1.0
    assert recall_at_k(['main."DIM_CAMPAIGN"'], {"dim_campaign"}, 3) == 1.0
    assert normalize_table_name('catalog.main.`DIM_CAMPAIGN`') == "dim_campaign"
