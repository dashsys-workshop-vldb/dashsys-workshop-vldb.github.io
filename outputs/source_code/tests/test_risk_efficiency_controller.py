from __future__ import annotations

from dashagent.risk_efficiency_controller import classify_candidate_risk


def test_low_risk_reports_expensive_modules_skipped_as_estimates():
    result = classify_candidate_risk(
        {
            "confidence": 0.95,
            "score_margin": 0.4,
            "schema_linking": {"schema_link_risk": "low"},
            "endpoint_family_ranking": {"endpoint_family_confidence": 0.91},
        }
    )
    assert result["risk_level"] == "low"
    assert "shadow_repair" in result["module_skipped_by_risk"]
    assert result["token_saved_estimate"] > 0
    assert result["runtime_saved_estimate_ms"] > 0
    assert result["savings_are_estimates"] is True
    assert result["measured_efficiency_improvement_claimed"] is False
    assert result["behavior_changed"] is False


def test_medium_risk_runs_ranking_policy_only():
    result = classify_candidate_risk(
        {
            "confidence": 0.62,
            "score_margin": 0.2,
            "schema_linking": {"schema_link_risk": "medium"},
            "endpoint_family_ranking": {"endpoint_family_confidence": 0.72},
        }
    )
    assert result["risk_level"] == "medium"
    assert result["modules_run_by_policy"] == ["hybrid_candidate_scoring", "endpoint_family_ranking"]
    assert "value_retrieval" in result["module_skipped_by_risk"]


def test_high_risk_reports_value_retrieval_shadow_repair_and_verifier():
    result = classify_candidate_risk(
        {
            "confidence": 0.22,
            "score_margin": 0.0,
            "schema_linking": {"schema_link_risk": "high"},
            "endpoint_family_ranking": {"endpoint_family_confidence": 0.31},
        },
        risk_cluster="zero_score_margin",
    )
    assert result["risk_level"] == "high"
    assert "value_retrieval" in result["modules_run_by_policy"]
    assert "shadow_repair" in result["modules_run_by_policy"]
    assert "repair_safety_verifier" in result["modules_run_by_policy"]
    assert result["module_skipped_by_risk"] == []
    assert result["token_saved_estimate"] == 0
