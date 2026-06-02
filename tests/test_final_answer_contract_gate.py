from __future__ import annotations

from dashagent.final_answer_contract_gate import check_final_answer_contract
from dashagent.answer_slots import extract_answer_slots
from dashagent.llm_final_answer_composer import build_llm_final_answer_card
from dashagent.llm_unified_planner import LLMUnifiedPass, LLMUnifiedPlan, LLMUnifiedSQLCandidate
from dashagent.result_bundle import ResultBundle
from dashagent.v2_answer_contract import parse_answer_contract
from dashagent.v2_evidence_contract import evaluate_evidence_contract


def _contract(slot_type: str, **updates):
    slot = {
        "slot_id": "s1",
        "type": slot_type,
        "required": True,
        "subject": updates.pop("subject", "Birthday Message"),
        "object": updates.pop("object", None),
        "relation": updates.pop("relation", None),
        "source_scope": updates.pop("source_scope", "LOCAL_SNAPSHOT"),
        "satisfied_by_tasks": updates.pop("satisfied_by_tasks", ["t1"]),
        "required_fields": updates.pop("required_fields", []),
        "acceptable_fallback_fields": updates.pop("acceptable_fallback_fields", []),
        "expected_status_filter": updates.pop("expected_status_filter", None),
        "zero_rows_semantics": updates.pop("zero_rows_semantics", "NO_MATCH"),
        "if_missing": updates.pop("if_missing", "SCOPED_UNAVAILABLE_CAVEAT"),
        "must_not_assert_positive_if_zero_rows": updates.pop("must_not_assert_positive_if_zero_rows", True),
        "notes": None,
    }
    slot.update(updates)
    return parse_answer_contract(
        {
            "required_slots": [slot],
            "optional_slots": [],
            "answer_style": "CAVEATED",
            "global_scope": slot["source_scope"],
            "contract_version": "v1",
        }
    )


def _runtime_pass(rows, *, status="SUCCESS", row_count=None, pass_id="t1", scope="LOCAL_SNAPSHOT"):
    if row_count is None:
        row_count = len(rows)
    return {
        "pass_id": pass_id,
        "path": "SQL",
        "source": "SQL",
        "status": status,
        "scope": scope,
        "source_results": [
            {
                "source": "SQL",
                "status": status,
                "scope": scope,
                "result": {"rows": rows, "row_count": row_count},
            }
        ],
    }


def test_contract_gate_rejects_positive_published_claim_without_date_field():
    contract = _contract(
        "DATE",
        relation="published_date",
        required_fields=["PUBLISHEDAT", "LASTDEPLOYEDTIME"],
        acceptable_fallback_fields=["CREATEDTIME"],
    )
    states = evaluate_evidence_contract(contract, [_runtime_pass([{"NAME": "Birthday Message"}])])

    result = check_final_answer_contract(
        "Birthday Message is published, but the publication date is not available.",
        answer_contract=contract,
        evidence_slot_states=states,
    )

    assert result.passed is False
    assert result.error_type in {"date_claim_unsupported", "unsupported_positive_claim", "missing_slot_coverage"}
    assert result.failed_slot_ids == ["s1"]


def test_contract_gate_rejects_positive_relation_when_relation_rows_zero():
    contract = _contract(
        "RELATION",
        subject="SMS Opt-In",
        object="destination",
        relation="audience_to_destination",
        required_fields=["SEGMENTID", "TARGETID"],
    )
    states = evaluate_evidence_contract(contract, [_runtime_pass([], status="EMPTY", row_count=0)])

    result = check_final_answer_contract(
        "SMS Opt-In is connected to the SMS Opt-In destination.",
        answer_contract=contract,
        evidence_slot_states=states,
    )

    assert result.passed is False
    assert result.error_type == "relation_claim_unsupported"


def test_contract_gate_rejects_zero_row_examples_include_phrase():
    contract = _contract("LIST", subject="_xdm.context.profile", required_fields=["NAME"])
    states = evaluate_evidence_contract(contract, [_runtime_pass([], status="EMPTY", row_count=0)])

    result = check_final_answer_contract(
        "Local snapshot evidence shows count 0; examples include _xdm.context.profile.",
        answer_contract=contract,
        evidence_slot_states=states,
    )

    assert result.passed is False
    assert result.error_type == "zero_row_positive_claim"


def test_contract_gate_rejects_raw_evidence_dump_for_count_slot():
    contract = _contract(
        "COUNT",
        subject="schemas",
        required_fields=["count"],
        zero_rows_semantics="EMPTY_RESULT_IS_ANSWER",
        if_missing="FAIL_REQUIRED",
        must_not_assert_positive_if_zero_rows=False,
    )
    states = evaluate_evidence_contract(contract, [_runtime_pass([{"count": 27}], row_count=1)])

    result = check_final_answer_contract(
        "Local snapshot evidence shows t2/SQL/LOCAL_SNAPSHOT: count: 27; relationship: BLUEPRINTID:abc -> COLLECTIONID:def.",
        answer_contract=contract,
        evidence_slot_states=states,
    )

    assert result.passed is False
    assert result.error_type == "answer_shape_error"


def test_contract_gate_allows_scoped_no_match_and_api_unavailable_caveats():
    relation = _contract("RELATION", subject="SMS Opt-In", object="destination", relation="audience_to_destination", required_fields=["SEGMENTID", "TARGETID"])
    relation_states = evaluate_evidence_contract(relation, [_runtime_pass([], status="EMPTY", row_count=0)])
    assert check_final_answer_contract(
        "No matching local snapshot relationship evidence was available for SMS Opt-In and destination.",
        answer_contract=relation,
        evidence_slot_states=relation_states,
    ).passed is True

    live = _contract("COUNT", subject="tags", source_scope="LIVE_API", required_fields=["count"], if_missing="SCOPED_UNAVAILABLE_CAVEAT")
    api_states = evaluate_evidence_contract(
        live,
        [{"pass_id": "t1", "path": "API", "source": "API", "status": "API_ERROR", "scope": "LIVE_API", "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API", "error": "credentials unavailable"}]}],
    )
    assert check_final_answer_contract(
        "Live API evidence for tags was unavailable, so the tag count cannot be verified.",
        answer_contract=live,
        evidence_slot_states=api_states,
    ).passed is True


def test_final_answer_card_includes_contract_and_evidence_slot_states():
    contract = _contract("COUNT", subject="schemas", required_fields=["count"], zero_rows_semantics="EMPTY_RESULT_IS_ANSWER")
    states = evaluate_evidence_contract(contract, [_runtime_pass([{"count": 74}], row_count=1)])
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="SQL_FIRST",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT COUNT(*) AS count FROM "dim_schema"', params=[]),
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="t1",
                subtask="Count schemas.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT COUNT(*) AS count FROM "dim_schema"', params=[]),
                api_request=None,
                expected_result="Schema count.",
            )
        ],
        aggregation_instruction="Answer with the schema count.",
        reason="test",
        provider="test",
        model="test",
        diagnostics={},
        answer_contract=contract,
    )

    card = build_llm_final_answer_card(
        user_prompt="How many schemas do I have?",
        llm_plan=plan,
        runtime_passes=[_runtime_pass([{"count": 74}], row_count=1)],
        evidence_bus=__import__("dashagent.evidence_bus", fromlist=["EvidenceBus"]).EvidenceBus(),
        answer_slots=extract_answer_slots("How many schemas do I have?", []),
        result_bundle=ResultBundle.from_pass_results([_runtime_pass([{"count": 74}], row_count=1)], []),
        answer_contract=contract,
        evidence_slot_states=states,
    )

    assert card["ANSWER_CONTRACT_REQUIRED_SLOTS"][0]["slot_id"] == "s1"
    assert card["EVIDENCE_SLOT_STATES"][0]["status"] == "SATISFIED"
    assert any("Answer every required answer contract slot" in item for item in card["constraints"])
