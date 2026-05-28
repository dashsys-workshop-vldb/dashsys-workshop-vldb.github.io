from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .evidence_allowed_fact_index import AllowedFactIndex
from .final_answer_claim_extractor import FinalAnswerClaim


MATCH_STATUSES = {"SUPPORTED", "UNSUPPORTED", "OVER_SPECIFIED", "NEEDS_CAVEAT", "AMBIGUOUS"}
GENERIC_ENTITY_NAMES = {
    "api",
    "sql",
    "evidence",
    "records",
    "record",
    "schema",
    "schemas",
    "dataset",
    "datasets",
    "campaign",
    "campaigns",
    "journey",
    "journeys",
    "status",
}


@dataclass(frozen=True)
class ClaimMatch:
    claim: FinalAnswerClaim
    status: str
    reason: str = ""

    def __post_init__(self) -> None:
        status = str(self.status or "UNSUPPORTED").upper()
        object.__setattr__(self, "status", status if status in MATCH_STATUSES else "UNSUPPORTED")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claim"] = self.claim.to_dict()
        return payload


def match_final_answer_claims(claims: list[FinalAnswerClaim], index: AllowedFactIndex) -> list[ClaimMatch]:
    return [match_final_answer_claim(claim, index) for claim in claims]


def match_final_answer_claim(claim: FinalAnswerClaim, index: AllowedFactIndex) -> ClaimMatch:
    claim_type = claim.type
    value = _normalize_text(claim.value)
    if claim.hardness == "SOFT" or claim_type == "SOFT_TEXT":
        return ClaimMatch(claim, "SUPPORTED", "soft_text")
    if claim_type == "COUNT":
        return _supported(claim, _norm_number(claim.value) in set(index.counts), "count")
    if claim_type == "ID":
        return _supported(claim, value in set(index.ids), "id")
    if claim_type == "STATUS":
        status = _normalize_status(claim.value)
        return _supported(claim, status in set(index.statuses), "status")
    if claim_type == "DATE":
        variants = _date_variants(claim.value)
        return _supported(claim, bool(set(variants) & set(index.dates)), "date")
    if claim_type == "ENTITY_NAME":
        if value in GENERIC_ENTITY_NAMES:
            return ClaimMatch(claim, "SUPPORTED", "generic_domain_term")
        return _entity_supported(claim, index)
    if claim_type == "EXISTENCE":
        if _name_supported(value, index):
            return ClaimMatch(claim, "SUPPORTED", "entity_exists_in_evidence")
        return ClaimMatch(claim, "AMBIGUOUS", "existence_claim_needs_semantic_judge")
    if claim_type == "RELATIONSHIP":
        return _supported(claim, value in set(index.relationships) or value in set(index.evidence_strings), "relationship")
    if claim_type == "NO_DATA":
        return _match_no_data(claim, index)
    if claim_type in {"LIVE_STATE", "CAVEAT"}:
        return _match_caveat(claim, index)
    return ClaimMatch(claim, "AMBIGUOUS", "unknown_claim_type")


def _entity_supported(claim: FinalAnswerClaim, index: AllowedFactIndex) -> ClaimMatch:
    value = _normalize_text(claim.value)
    if _name_supported(value, index):
        return ClaimMatch(claim, "SUPPORTED", "entity_name")
    if any(value in evidence or evidence in value for evidence in index.evidence_strings if len(evidence) >= 4):
        return ClaimMatch(claim, "SUPPORTED", "evidence_string")
    return ClaimMatch(claim, "UNSUPPORTED", "entity_name_not_in_allowed_facts")


def _name_supported(value: str, index: AllowedFactIndex) -> bool:
    if value in set(index.names):
        return True
    return any(value in name or name in value for name in index.names if len(name) >= 4)


def _match_no_data(claim: FinalAnswerClaim, index: AllowedFactIndex) -> ClaimMatch:
    value = _normalize_text(claim.text or claim.value)
    has_empty_caveat = bool(set(index.allowed_caveats) & {"API_LIVE_EMPTY", "SQL_EMPTY"})
    has_api_error_only = "API_ERROR" in set(index.allowed_caveats) and not has_empty_caveat
    if has_api_error_only:
        return ClaimMatch(claim, "NEEDS_CAVEAT", "api_error_is_not_no_data")
    if not has_empty_caveat:
        return ClaimMatch(claim, "UNSUPPORTED", "no_empty_evidence")
    if "anywhere" in value or "globally" in value:
        return ClaimMatch(claim, "OVER_SPECIFIED", "live_empty_is_scoped_not_global")
    if re.search(r"\bthere are no\b", value) and "matching" not in value and "query" not in value and "scope" not in value:
        return ClaimMatch(claim, "OVER_SPECIFIED", "live_empty_is_scoped_not_global")
    if "matching" in value or "query" in value or "scope" in value or "returned no" in value:
        return ClaimMatch(claim, "SUPPORTED", "scoped_empty")
    return ClaimMatch(claim, "NEEDS_CAVEAT", "empty_claim_needs_scope")


def _match_caveat(claim: FinalAnswerClaim, index: AllowedFactIndex) -> ClaimMatch:
    value = _normalize_text(claim.text or claim.value)
    if ("unavailable" in value or "error" in value or "could not be verified" in value or "cannot verify" in value) and (
        set(index.allowed_caveats) & {"API_ERROR", "DRY_RUN_UNAVAILABLE"}
    ):
        return ClaimMatch(claim, "SUPPORTED", "api_error_or_unavailable_caveat")
    if "no matching" in value and "API_LIVE_EMPTY" in set(index.allowed_caveats):
        return ClaimMatch(claim, "SUPPORTED", "live_empty_caveat")
    return ClaimMatch(claim, "AMBIGUOUS", "caveat_not_directly_matched")


def _supported(claim: FinalAnswerClaim, ok: bool, reason: str) -> ClaimMatch:
    return ClaimMatch(claim, "SUPPORTED" if ok else "UNSUPPORTED", reason if ok else f"{reason}_not_in_allowed_facts")


def _normalize_status(value: Any) -> str:
    text = _normalize_text(value)
    return {"success": "succeeded", "successful": "succeeded", "failure": "failed"}.get(text, text)


def _date_variants(value: Any) -> list[str]:
    text = str(value)
    out = [_normalize_text(text)]
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    if match:
        out.append(match.group(0).lower())
    return list(dict.fromkeys(out))


def _norm_number(value: Any) -> str:
    return re.sub(r"[^\d.]", "", str(value))


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())
