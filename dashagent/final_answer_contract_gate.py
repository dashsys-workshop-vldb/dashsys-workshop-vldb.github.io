from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .v2_answer_contract import EvidenceSlotState, V2AnswerContract


@dataclass
class FinalAnswerContractGateResult:
    passed: bool
    error_type: str | None = None
    message: str | None = None
    failed_slot_ids: list[str] = field(default_factory=list)
    slot_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_final_answer_contract(
    final_answer: str,
    *,
    answer_contract: V2AnswerContract | None,
    evidence_slot_states: list[EvidenceSlotState],
) -> FinalAnswerContractGateResult:
    if answer_contract is None:
        return FinalAnswerContractGateResult(True)
    answer = str(final_answer or "")
    normalized = _norm(answer)
    state_by_id = {state.slot_id: state for state in evidence_slot_states}
    slot_results: list[dict[str, Any]] = []
    for slot in answer_contract.required_slots:
        state = state_by_id.get(slot.slot_id)
        if state is None:
            return _fail("missing_slot_coverage", f"Missing evidence state for required slot {slot.slot_id}.", [slot.slot_id], slot_results)
        check = _check_slot(answer, normalized, slot, state)
        slot_results.append({"slot_id": slot.slot_id, "status": state.status, "passed": check[0], "error_type": check[1], "message": check[2]})
        if not check[0]:
            return _fail(check[1] or "missing_slot_coverage", check[2] or "Final answer does not satisfy answer contract.", [slot.slot_id], slot_results)
    return FinalAnswerContractGateResult(True, slot_results=slot_results)


def _check_slot(answer: str, normalized: str, slot: Any, state: EvidenceSlotState) -> tuple[bool, str | None, str | None]:
    if _looks_like_raw_evidence_dump(answer):
        return False, "answer_shape_error", "Final answer contains raw pass/evidence fragments instead of user-facing slot coverage."
    if state.status == "SATISFIED":
        return _check_satisfied_slot(answer, normalized, slot, state)
    if state.status == "PARTIAL":
        if slot.type == "DATE" and _contains_positive_date_relation_claim(normalized, slot) and not state.date_values:
            return False, "date_claim_unsupported", "Date/published claim is not supported by required or fallback date evidence."
        if _has_scoped_caveat(normalized, state):
            return True, None, None
        if state.facts or state.list_rows or state.count_values:
            return True, None, None
        return False, "missing_slot_coverage", "Partial slot requires available facts and a scoped caveat."
    if state.status == "ZERO_ROWS":
        if _contains_positive_existence_claim(normalized, slot):
            if slot.type == "RELATION":
                return False, "relation_claim_unsupported", "Positive relation claim is not allowed for zero-row relation evidence."
            return False, "zero_row_positive_claim", "Positive existence/example claim is not allowed for zero-row evidence."
        if _has_no_match_caveat(normalized):
            return True, None, None
        return False, "missing_slot_coverage", "Zero-row slot requires scoped no-match wording."
    if state.status == "API_UNAVAILABLE":
        if _turns_api_error_into_no_data(normalized):
            return False, "scope_caveat_error", "API_ERROR supports unavailable caveat, not no-data."
        if _has_api_unavailable_caveat(normalized):
            return True, None, None
        return False, "missing_slot_coverage", "API unavailable slot requires scoped API unavailable caveat."
    if state.status in {"NO_EVIDENCE", "ERROR", "DEPENDENCY_FAILED"}:
        if _has_unavailable_caveat(normalized):
            return True, None, None
        return False, "missing_slot_coverage", "Missing/error slot requires scoped unavailable caveat."
    return True, None, None


def _check_satisfied_slot(answer: str, normalized: str, slot: Any, state: EvidenceSlotState) -> tuple[bool, str | None, str | None]:
    if slot.type == "COUNT":
        if not state.count_values:
            return False, "missing_slot_coverage", "COUNT slot is satisfied only with count evidence."
        if not any(str(value) in answer for value in state.count_values):
            return False, "missing_slot_coverage", "Final answer omits required count value."
    if slot.type == "DATE":
        if state.date_values and not any(str(value) in answer for value in state.date_values):
            return False, "date_claim_unsupported", "Final answer omits supported date value."
        if not state.date_values and _contains_positive_date_relation_claim(normalized, slot):
            return False, "date_claim_unsupported", "Date/published claim is not supported by date evidence."
    if slot.type == "STATUS":
        if state.status_values and not any(_norm(value) in normalized for value in state.status_values):
            return False, "missing_slot_coverage", "Final answer omits required status value."
    if slot.type == "RELATION":
        if not state.relation_rows:
            return False, "relation_claim_unsupported", "Relationship/connection claim requires relation rows."
    if slot.type in {"LIST", "LOOKUP"}:
        if not state.list_rows and not state.facts:
            return False, "missing_slot_coverage", "LIST/LOOKUP slot requires rows or scoped caveat."
    return True, None, None


def _looks_like_raw_evidence_dump(answer: str) -> bool:
    text = str(answer or "")
    return bool(re.search(r"\b[a-zA-Z0-9_-]+/(?:SQL|API)/(?:LOCAL_SNAPSHOT|LIVE_API)\b", text)) or "relationship:" in text.lower()


def _contains_positive_date_relation_claim(normalized: str, slot: Any) -> bool:
    relation = _norm(getattr(slot, "relation", None))
    date_words = {"published", "deployed", "created", "updated", "modified"}
    if relation and any(word in relation for word in date_words):
        return any(word in normalized for word in date_words)
    return False


def _contains_positive_existence_claim(normalized: str, slot: Any) -> bool:
    positive_markers = [
        " is connected ",
        " are connected ",
        " connected to ",
        " mapped to ",
        " belongs to ",
        " used in ",
        " examples include ",
        " include ",
        " includes ",
        " found ",
        " exists ",
    ]
    if any(marker.strip() in normalized for marker in positive_markers):
        return True
    subject = _norm(getattr(slot, "subject", None))
    obj = _norm(getattr(slot, "object", None))
    if subject and obj and subject in normalized and obj in normalized and "no matching" not in normalized:
        return any(word in normalized for word in ["connected", "mapped", "used", "include", "exists"])
    return False


def _has_scoped_caveat(normalized: str, state: EvidenceSlotState) -> bool:
    scope = _norm(state.source_scope)
    return bool(scope and scope in normalized and any(word in normalized for word in ["unavailable", "not available", "missing", "could not", "cannot"]))


def _has_no_match_caveat(normalized: str) -> bool:
    return "no matching" in normalized or "no match" in normalized or "zero matching" in normalized


def _has_api_unavailable_caveat(normalized: str) -> bool:
    return ("api" in normalized or "live" in normalized) and any(word in normalized for word in ["unavailable", "not available", "failed", "credentials", "cannot", "could not"])


def _has_unavailable_caveat(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ["unavailable", "not available", "could not", "cannot provide", "cannot verify", "missing"])


def _turns_api_error_into_no_data(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ["no records", "no schemas", "no tags", "none exist", "zero records", "no data"]) and not _has_api_unavailable_caveat(normalized)


def _fail(error_type: str, message: str, failed_slot_ids: list[str], slot_results: list[dict[str, Any]]) -> FinalAnswerContractGateResult:
    return FinalAnswerContractGateResult(False, error_type=error_type, message=message, failed_slot_ids=failed_slot_ids, slot_results=slot_results)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()
