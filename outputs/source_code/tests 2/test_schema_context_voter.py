from __future__ import annotations

from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.executor import AgentExecutor
from dashagent.schema_context_voter import vote_schema_contexts


def test_schema_voting_marks_agreement_safe(tiny_project):
    executor = AgentExecutor(tiny_project)
    vote = vote_schema_contexts(
        query="How many campaigns are present?",
        compact_context={
            "candidate_tables": ["dim_campaign"],
            "candidate_apis": [{"id": "journey_list"}],
            "estimated_tokens": 80,
        },
        schema_index=executor.schema_index,
        endpoint_catalog=EndpointCatalog(tiny_project),
        risk_level="high",
    )
    assert vote["active"] is True
    assert vote["schema_vote_agreement"] is True
    assert vote["compact_context_safe"] is True
    assert vote["behavior_changed"] is False


def test_schema_voting_disagreement_records_fallback_reason(tiny_project):
    executor = AgentExecutor(tiny_project)
    vote = vote_schema_contexts(
        query="How many campaigns are present?",
        compact_context={
            "candidate_tables": ["dim_segment"],
            "candidate_apis": [{"id": "segment_definitions"}],
            "estimated_tokens": 80,
        },
        schema_index=executor.schema_index,
        endpoint_catalog=EndpointCatalog(tiny_project),
        risk_level="high",
    )
    assert vote["active"] is True
    assert vote["schema_vote_agreement"] is False
    assert vote["compact_context_safe"] is False
    assert "disagrees" in vote["fallback_reason"]


def test_schema_voting_skips_low_risk_diagnostics(tiny_project):
    executor = AgentExecutor(tiny_project)
    vote = vote_schema_contexts(
        query="How many campaigns are present?",
        compact_context={"candidate_tables": ["dim_campaign"], "estimated_tokens": 80},
        schema_index=executor.schema_index,
        endpoint_catalog=EndpointCatalog(tiny_project),
        risk_level="low",
    )
    assert vote["active"] is False
    assert vote["diagnostic_only"] is True
    assert vote["schema_vote_agreement"] is None
