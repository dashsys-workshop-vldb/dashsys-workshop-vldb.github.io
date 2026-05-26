from __future__ import annotations

from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.weak_model_semantic_slots import normalize_semantic_slots


def _slots(prompt: str):
    return normalize_semantic_slots({}, prompt=prompt)


def test_balanced_evidence_need_keeps_sql_lift_without_suppressing_api():
    from dashagent.weak_model_semantic_slots import classify_balanced_evidence_need

    journey_slots = _slots("List all journeys")
    assert classify_balanced_evidence_need("List all journeys", journey_slots) == "sql_primary_api_verify"

    live_slots = _slots("Use the live Adobe API to list audience segments")
    assert classify_balanced_evidence_need("Use the live Adobe API to list audience segments", live_slots) == "api_primary_sql_context"

    mixed_slots = _slots("List all segment audiences connected to the destination named 'SMS Opt-In'")
    assert classify_balanced_evidence_need("List all segment audiences connected to the destination named 'SMS Opt-In'", mixed_slots) == "sql_then_api"


def test_endpoint_selector_recovers_catalog_families_without_path_params(tiny_project):
    from dashagent.weak_model_api_selector import select_weak_model_api_candidates

    catalog = EndpointCatalog(tiny_project)

    journey = select_weak_model_api_candidates(_slots("List all journeys"), catalog)
    assert journey["selected_endpoint"]["endpoint_id"] == "journey_list"
    assert "{" not in journey["selected_endpoint"]["path"]

    segment = select_weak_model_api_candidates(_slots("List all segment audiences"), catalog)
    assert segment["selected_endpoint"]["endpoint_id"] in {"ups_audiences", "segment_definitions"}

    flow = select_weak_model_api_candidates(_slots("Show failed dataflow runs"), catalog)
    assert flow["selected_endpoint"]["endpoint_id"] in {"flowservice_flows", "flowservice_runs"}

    tag = select_weak_model_api_candidates(_slots("List tag categories"), catalog)
    assert tag["selected_endpoint"]["endpoint_id"] == "unified_tag_categories"


def test_api_evidence_bridge_distinguishes_success_empty_and_error():
    from dashagent.weak_model_api_evidence_bridge import build_api_evidence

    success = build_api_evidence(
        "journey_list",
        {
            "ok": True,
            "endpoint": "/ajo/journey",
            "parsed_evidence": {
                "evidence_state": "live_success",
                "ids": ["j1"],
                "names": ["Birthday Message"],
                "statuses": ["live"],
                "timestamps": ["2026-03-31T00:00:00Z"],
                "counts": [1],
            },
        },
    )
    assert success["live_success"] is True
    assert success["names"] == ["Birthday Message"]

    empty = build_api_evidence("journey_list", {"ok": True, "parsed_evidence": {"evidence_state": "live_empty"}})
    assert empty["live_empty"] is True
    assert empty["api_error"] is False

    error = build_api_evidence("journey_list", {"ok": False, "status_code": 500, "error": "server unavailable"})
    assert error["api_error"] is True
    assert error["live_empty"] is False


def test_answer_grounder_uses_required_api_evidence_and_keeps_claims_supported():
    from dashagent.weak_model_answer_grounder import ground_weak_model_answer

    result = ground_weak_model_answer(
        "List all journeys",
        model_answer="",
        sql_result={"ok": True, "row_count": 1, "rows": [{"NAME": "Birthday Message", "CAMPAIGNID": "j1"}]},
        api_result={
            "ok": True,
            "endpoint": "/ajo/journey",
            "parsed_evidence": {"evidence_state": "live_success", "names": ["Birthday Message"], "ids": ["j1"]},
        },
        answer_intent="LIST",
        evidence_need="sql_primary_api_verify",
        api_endpoint_id="journey_list",
    )

    assert result["answer_used_sql"] is True
    assert result["answer_used_api"] is True
    assert result["api_evidence_object_available"] is True
    assert "Birthday Message" in result["answer"]
    assert result["unsupported_claim_count"] == 0


def test_balanced_variants_are_shadow_only(tiny_project):
    from scripts.run_weak_model_lift_eval import WEAK_MODEL_VARIANTS, run_weak_model_lift_eval

    assert "weak_scaffold_balanced_full_v1" in WEAK_MODEL_VARIANTS
    payload = run_weak_model_lift_eval(tiny_project, max_examples=1, variants=["weak_scaffold_balanced_full_v1"], execute_real=False)

    assert payload["diagnostic_only"] is True
    assert payload["promotion_allowed"] is False
    assert payload["packaged_runtime_changed"] is False
