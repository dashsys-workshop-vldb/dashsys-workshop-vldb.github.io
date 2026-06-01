from __future__ import annotations

import json

from dashagent.answer_slots import extract_answer_slots
from dashagent.evidence_bus import EvidenceBus
from dashagent.final_answer_claim_extractor import extract_final_answer_claims
from dashagent.llm_final_answer_composer import (
    build_llm_final_answer_card,
    check_final_answer_semantic_grounding,
    check_final_answer_syntax,
    parse_llm_final_answer_response,
    safe_llm_final_answer_fallback,
)
from dashagent.llm_unified_planner import LLMUnifiedAPIRequest, LLMUnifiedPass, LLMUnifiedPlan, LLMUnifiedSQLCandidate
from dashagent.planner import PlanStep
from dashagent.result_bundle import ResultBundle


def _sql_tool_result(rows: list[dict]) -> dict:
    return {
        "type": "sql",
        "step": {"action": "sql", "purpose": "test", "sql": "SELECT * FROM dim_campaign"},
        "payload": {"ok": True, "rows": rows, "row_count": len(rows)},
    }


def _api_tool_result(parsed_evidence: dict) -> dict:
    return {
        "type": "api",
        "step": {"action": "api", "method": "GET", "url": "/test", "params": {}, "family": "llm_owned_v2"},
        "payload": {"ok": True, "parsed_evidence": parsed_evidence},
    }


def _bus_and_slots(prompt: str, tool_results: list[dict]) -> tuple[EvidenceBus, object]:
    bus = EvidenceBus()
    for item in tool_results:
        step_payload = item.get("step") or {}
        step = PlanStep(action=step_payload.get("action", ""), purpose="test", sql=step_payload.get("sql"), method=step_payload.get("method"), url=step_payload.get("url"), params=step_payload.get("params") or {}, family=step_payload.get("family"))
        if item["type"] == "sql":
            bus.observe_sql(step, item["payload"])
        if item["type"] == "api":
            bus.observe_api(step, item["payload"])
    return bus, extract_answer_slots(prompt, tool_results)


def test_syntax_gate_accepts_valid_wrapper_and_rejects_empty_or_malformed_answer():
    parsed = parse_llm_final_answer_response(
        json.dumps(
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            }
        )
    )

    assert check_final_answer_syntax(parsed).passed is True
    assert check_final_answer_syntax(parse_llm_final_answer_response("{}")).passed is False
    assert check_final_answer_syntax(parse_llm_final_answer_response("not json")).passed is False


def test_semantic_gate_rejects_unsupported_count_claim():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are 3 campaigns.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "unsupported_claim"
    assert result.unsupported_claims


def test_semantic_gate_rejects_status_contradiction():
    tool_results = [_sql_tool_result([{"name": "Birthday Message", "status": "draft"}])]
    bus, slots = _bus_and_slots("What is the status of Birthday Message?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Birthday Message is published.",
        question="What is the status of Birthday Message?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"name": "Birthday Message", "status": "draft"}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "contradiction"


def test_semantic_gate_rejects_missing_required_count_when_evidence_contains_it():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Campaign records were found.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "missing_required_info"
    assert "count" in result.missing_required_fields


def test_semantic_gate_rejects_local_live_scope_confusion():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many current schemas are in Adobe Experience Platform?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Adobe Experience Platform currently has 2 schemas.",
        question="How many current schemas are in Adobe Experience Platform?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "scope_error"


def test_semantic_gate_rejects_api_error_as_no_data():
    tool_results = [
        {
            "type": "api",
            "step": {"action": "api", "method": "GET", "url": "/test", "params": {}, "family": "llm_owned_v2"},
            "payload": {"ok": False, "dry_run": False, "error": "API unavailable"},
        }
    ]
    bus, slots = _bus_and_slots("Show current schemas.", tool_results)

    result = check_final_answer_semantic_grounding(
        "No schemas were returned.",
        question="Show current schemas.",
        runtime_passes=[{"pass_id": "api_1", "source": "API", "status": "API_ERROR", "scope": "LIVE_API", "result": {}, "caveats": ["API unavailable"]}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "caveat_error"


def test_semantic_gate_allows_api_failed_wording_as_caveat_not_status_claim():
    tool_results = [
        _sql_tool_result([{"name": "Birthday Message", "status": "updated"}]),
        {
            "type": "api",
            "step": {"action": "api", "method": "GET", "url": "/ajo/journey", "params": {}, "family": "llm_owned_v2"},
            "payload": {"ok": False, "dry_run": True, "error": "Adobe credentials unavailable"},
        },
    ]
    bus, slots = _bus_and_slots("Compare local and live status of Birthday Message if both are available.", tool_results)

    result = check_final_answer_semantic_grounding(
        'From the local snapshot, Birthday Message has status "updated". The live API call failed because Adobe credentials were unavailable.',
        question="Compare local and live status of Birthday Message if both are available.",
        runtime_passes=[
            {
                "pass_id": "local_status",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["status: updated", "name: Birthday Message"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {"rows": [{"name": "Birthday Message", "status": "updated"}]},
            },
            {
                "pass_id": "live_status",
                "source": "API",
                "status": "API_ERROR",
                "scope": "LIVE_API",
                "facts": [],
                "caveats": ["Adobe credentials unavailable"],
                "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API"}],
                "result": {},
            },
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_claim_extractor_treats_sentence_final_number_as_count():
    claims = extract_final_answer_claims("The count of schema records in the local snapshot is 10.")

    assert any(claim.type == "COUNT" and claim.value == "10" for claim in claims)


def test_claim_extractor_treats_deployed_time_as_timestamp_wording_not_status():
    claims = extract_final_answer_claims(
        'The local snapshot found "Birthday Message" but did not provide a last deployed time. Live API verification failed because credentials were unavailable.'
    )

    assert not any(claim.type == "STATUS" and claim.value.lower() == "deployed" for claim in claims)
    assert not any(claim.type == "STATUS" and claim.value.lower() == "failed" for claim in claims)


def test_semantic_gate_allows_draft_as_conceptual_example_when_data_statuses_differ():
    tool_results = [_sql_tool_result([{"name": "Birthday Message", "status": "updated"}, {"name": "Gold Tier Welcome Email", "status": "created"}])]
    bus, slots = _bus_and_slots("Explain inactive journey and show inactive journeys.", tool_results)

    result = check_final_answer_semantic_grounding(
        'An inactive journey can include a journey in a draft state or one that is not running. Local snapshot journeys: Birthday Message has status "updated"; Gold Tier Welcome Email has status "created".',
        question="Explain inactive journey and show inactive journeys.",
        runtime_passes=[
            {
                "pass_id": "local_inactive",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["name: Birthday Message", "status: updated", "name: Gold Tier Welcome Email", "status: created"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {"rows": [{"name": "Birthday Message", "status": "updated"}, {"name": "Gold Tier Welcome Email", "status": "created"}]},
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_rejects_live_empty_as_global_absence():
    tool_results = [_api_tool_result({"evidence_state": "live_empty", "live_evidence_available": True, "counts": {"items": 0}, "names": []})]
    bus, slots = _bus_and_slots("Show current schemas.", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are no schemas in Adobe Experience Platform.",
        question="Show current schemas.",
        runtime_passes=[{"pass_id": "api_1", "source": "API", "status": "LIVE_EMPTY", "scope": "LIVE_API", "result": {}, "caveats": []}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "caveat_error"


def test_final_answer_card_requires_partial_local_evidence_before_api_caveat():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="MULTI_PASS",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
        api_request=LLMUnifiedAPIRequest(method="GET", path="/ajo/journey", params={}),
        passes=[
            LLMUnifiedPass(
                pass_id="local_status",
                subtask="Retrieve local status.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
                api_request=None,
                expected_result="Local status.",
            ),
            LLMUnifiedPass(
                pass_id="live_status",
                subtask="Retrieve live status.",
                path="API",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="API_FIRST",
                sql=None,
                api_request=LLMUnifiedAPIRequest(method="GET", path="/ajo/journey", params={}),
                expected_result="Live status.",
            ),
        ],
        aggregation_instruction="Use local evidence and include live API caveat if live fails.",
        reason="test",
        provider="openai",
        model="unit",
    )
    runtime_passes = [
        {
            "pass_id": "local_status",
            "source": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["name: Birthday Message", "status: updated"],
            "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
        },
        {
            "pass_id": "live_status",
            "source": "API",
            "status": "API_ERROR",
            "scope": "LIVE_API",
            "facts": [],
            "caveats": ["Adobe credentials unavailable"],
            "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API"}],
        },
    ]
    evidence_bus = EvidenceBus(run_id="unit")
    for item in runtime_passes:
        evidence_bus.observe_pass_result(item)
    slots = extract_answer_slots(
        "Compare local and live status of Birthday Message if both are available.",
        [
            _sql_tool_result([{"name": "Birthday Message", "status": "updated"}]),
            {
                "type": "api",
                "step": {"action": "api", "method": "GET", "url": "/ajo/journey", "params": {}, "family": "llm_owned_v2"},
                "payload": {"ok": False, "dry_run": True, "error": "Adobe credentials unavailable"},
            },
        ],
    )
    bundle = ResultBundle.from_pass_results(runtime_passes, [], run_id="unit")

    card = build_llm_final_answer_card(
        user_prompt="Compare local and live status of Birthday Message if both are available.",
        llm_plan=plan,
        runtime_passes=runtime_passes,
        evidence_bus=evidence_bus,
        answer_slots=slots,
        result_bundle=bundle,
        aggregation_instruction=plan.aggregation_instruction,
    )

    constraints = " ".join(card["constraints"])
    assert "If any required local evidence succeeded" in constraints
    assert "Only use the global runtime-unavailable answer if all required evidence failed" in constraints


def test_safe_error_fallback_uses_semantic_gate_safe_wording():
    answer = safe_llm_final_answer_fallback([{"status": "ERROR"}])
    bus, slots = _bus_and_slots("When was the journey Birthday Message published?", [])

    result = check_final_answer_semantic_grounding(
        answer,
        question="When was the journey Birthday Message published?",
        runtime_passes=[{"pass_id": "p1", "status": "ERROR", "source_results": []}],
        evidence_bus=bus,
        slots=slots,
    )

    assert answer == "Runtime evidence was unavailable; cannot provide a verified answer."
    assert result.passed is True


def test_semantic_gate_allows_extra_correct_context_without_gold_wording():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are 2 campaigns. This count comes from the runtime SQL evidence.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True
    serialized = json.dumps(result.to_dict(), sort_keys=True).lower()
    assert "gold_answer" not in serialized
    assert "expected_trace" not in serialized


def test_semantic_gate_catches_ignored_necessary_pass_result():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("Count campaigns locally and verify the live API result.", tool_results)
    bus.api_names.append("Birthday Message")

    result = check_final_answer_semantic_grounding(
        "There are 2 campaigns.",
        question="Count campaigns locally and verify the live API result.",
        runtime_passes=[
            {
                "pass_id": "local_count",
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
                "facts": ["count:2"],
                "caveats": [],
            },
            {
                "pass_id": "live_probe",
                "source_results": [{"source": "API", "status": "SUCCESS", "scope": "LIVE_API", "result": {"parsed_evidence": {"names": ["Birthday Message"]}}}],
                "facts": ["names:Birthday Message"],
                "caveats": [],
            },
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "missing_required_info"
    assert "pass:live_probe" in result.missing_required_fields
