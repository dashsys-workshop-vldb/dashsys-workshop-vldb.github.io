from __future__ import annotations

from dashagent.candidate_context_builder import choose_context_mode


def test_candidate_context_policy_high_confidence_uses_candidate():
    assert choose_context_mode({"confidence": 0.9, "score_margin": 0.2, "candidate_tables": ["dim_campaign"]}) == "candidate"


def test_candidate_context_policy_medium_confidence_expands():
    assert choose_context_mode({"confidence": 0.55, "score_margin": 0.2, "candidate_tables": ["dim_campaign"]}) == "expanded_candidate"


def test_candidate_context_policy_low_confidence_uses_hybrid():
    assert choose_context_mode({"confidence": 0.2, "score_margin": 0.1, "candidate_tables": ["dim_campaign"]}) == "hybrid"


def test_candidate_context_policy_empty_candidates_uses_full_schema():
    assert choose_context_mode({"confidence": 0.2, "score_margin": 0.0, "candidate_tables": [], "candidate_apis": []}) == "full_schema"


def test_candidate_context_policy_zero_margin_uses_hybrid():
    assert choose_context_mode({"confidence": 0.8, "score_margin": 0.0, "candidate_tables": ["dim_campaign"]}) == "hybrid"
