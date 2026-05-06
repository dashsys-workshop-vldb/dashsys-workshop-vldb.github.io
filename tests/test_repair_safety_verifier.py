from __future__ import annotations

from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.executor import AgentExecutor
from dashagent.repair_safety_verifier import verify_repair_safety


def _trajectory(unsupported: int = 0) -> dict:
    return {
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_16_answer_verification",
                "output": {"unsupported_claims_count": unsupported, "verifier_passed": unsupported == 0},
            }
        ]
    }


def test_repair_safety_accepts_valid_catalog_backed_replacement(tiny_project):
    executor = AgentExecutor(tiny_project)
    current = {
        "sql": ["SELECT COUNT(*) AS count FROM dim_campaign"],
        "api_calls": [{"method": "GET", "path": "/ajo/journey", "params": {}}],
        "tool_call_count": 2,
        "expected_answer_shape": "journey_list",
    }
    repaired = {
        **current,
        "fusion_agreement": True,
        "endpoint_family_confidence": 0.95,
        "dry_run_only": True,
        "live_api_evidence_available": False,
    }

    verdict = verify_repair_safety(current, repaired, _trajectory(), executor.schema_index, EndpointCatalog(tiny_project))

    assert verdict["safe"] is True
    assert verdict["failed_checks"] == []


def test_repair_safety_rejects_invalid_sql_endpoint_and_cost(tiny_project):
    executor = AgentExecutor(tiny_project)
    current = {
        "sql": ["SELECT COUNT(*) AS count FROM dim_campaign"],
        "api_calls": [{"method": "GET", "path": "/ajo/journey", "params": {}}],
        "tool_call_count": 2,
        "expected_answer_shape": "count",
    }
    repaired = {
        "sql": ["DROP TABLE dim_campaign"],
        "api_calls": [{"method": "GET", "path": "/not/a/catalog/path", "params": {}}],
        "tool_call_count": 3,
        "expected_answer_shape": "count",
        "fusion_agreement": False,
        "endpoint_family_confidence": 0.2,
        "dry_run_only": True,
        "live_api_evidence_available": True,
    }

    verdict = verify_repair_safety(current, repaired, _trajectory(unsupported=1), executor.schema_index, EndpointCatalog(tiny_project))

    assert verdict["safe"] is False
    for check in [
        "sql_validation",
        "api_validation",
        "tool_call_increase",
        "fusion_agreement",
        "endpoint_family_confidence",
        "dry_run_live_evidence",
        "unsupported_claims",
    ]:
        assert check in verdict["failed_checks"]
