from __future__ import annotations

import json

from dashagent.answer_slots import extract_answer_slots
from dashagent.evidence_bus import EvidenceBus
from dashagent.llm_final_answer_composer import (
    check_final_answer_semantic_grounding,
    check_final_answer_syntax,
    parse_llm_final_answer_response,
)
from dashagent.planner import PlanStep


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
