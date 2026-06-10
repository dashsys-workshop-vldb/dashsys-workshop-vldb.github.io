from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .answer_claims import AnswerClaim, extract_availability_claims, extract_claims
from .answer_slots import AnswerSlots
from .answer_verifier import verify_answer


@dataclass(frozen=True)
class FaithfulnessReport:
    claims: list[dict[str, Any]]
    supported_claims: list[dict[str, Any]]
    unsupported_claims: list[dict[str, Any]]
    faithfulness_score: float
    answer_relevance_flags: list[str] = field(default_factory=list)
    unused_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims": self.claims,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "faithfulness_score": self.faithfulness_score,
            "answer_relevance_flags": self.answer_relevance_flags,
            "unused_evidence": self.unused_evidence,
        }


def evaluate_answer_faithfulness(answer: str, slots: AnswerSlots) -> FaithfulnessReport:
    claims = extract_claims(answer) + extract_availability_claims(answer)
    verification = verify_answer(answer, slots)
    unsupported_values = {(claim.claim_type, claim.value) for claim in verification.unsupported_claims}
    extra_unsupported = _availability_drift(answer, slots)
    unsupported_values.update((claim.claim_type, claim.value) for claim in extra_unsupported)

    claim_dicts = [_claim_dict(claim) for claim in claims + extra_unsupported]
    unsupported = [_claim_dict(claim) for claim in claims + extra_unsupported if (claim.claim_type, claim.value) in unsupported_values]
    supported = [_claim_dict(claim) for claim in claims if (claim.claim_type, claim.value) not in unsupported_values]
    total = max(1, len(claim_dicts))
    score = round(max(0.0, 1.0 - (len(unsupported) / total)), 4)
    flags = _relevance_flags(answer, slots)
    unused = _unused_evidence(answer, slots)
    return FaithfulnessReport(
        claims=claim_dicts,
        supported_claims=supported,
        unsupported_claims=unsupported,
        faithfulness_score=score,
        answer_relevance_flags=flags,
        unused_evidence=unused,
    )


def unsupported_claim_count(answer: str, slots: AnswerSlots) -> int:
    return len(evaluate_answer_faithfulness(answer, slots).unsupported_claims)


def _availability_drift(answer: str, slots: AnswerSlots) -> list[AnswerClaim]:
    lowered = answer.lower()
    unsupported: list[AnswerClaim] = []
    if "credentials" in lowered and "unavailable" in lowered and not slots.dry_run:
        unsupported.append(AnswerClaim("unsupported_availability", "credentials_unavailable_without_dry_run"))
    if any(token in lowered for token in ["no matching", "returned no", "no data", "not found"]):
        live_empty = slots.api_evidence_state in {"live_empty", "live_empty_result"}
        sql_empty = slots.sql_row_count == 0 and not slots.dry_run
        if not live_empty and not sql_empty:
            unsupported.append(AnswerClaim("unsupported_availability", "empty_result_without_empty_evidence"))
    if "api request failed" in lowered and not slots.api_error:
        unsupported.append(AnswerClaim("unsupported_availability", "api_error_without_api_error"))
    if "could not be parsed" in lowered and slots.api_evidence_state != "malformed_response":
        unsupported.append(AnswerClaim("unsupported_availability", "malformed_without_malformed_response"))
    return unsupported


def _relevance_flags(answer: str, slots: AnswerSlots) -> list[str]:
    flags: list[str] = []
    lowered = answer.lower()
    if slots.dry_run and "unavailable" not in lowered and "credentials" not in lowered:
        flags.append("missing_dry_run_caveat")
    if slots.api_evidence_state in {"live_empty", "live_empty_result"} and "credentials" in lowered:
        flags.append("answer_confuses_live_empty_with_dry_run")
    return flags


def _unused_evidence(answer: str, slots: AnswerSlots) -> list[str]:
    lowered = answer.lower()
    unused: list[str] = []
    for label, values in [
        ("names", slots.entity_names),
        ("ids", slots.entity_ids),
        ("statuses", slots.statuses),
        ("timestamps", slots.timestamps),
        ("counts", [str(value) for value in slots.counts]),
    ]:
        if values and not any(str(value).lower() in lowered for value in values[:5]):
            unused.append(label)
    return unused


def _claim_dict(claim: AnswerClaim) -> dict[str, Any]:
    return {
        "claim_type": claim.claim_type,
        "value": claim.value,
        "start": claim.start,
        "end": claim.end,
    }
