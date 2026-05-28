from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_slots import AnswerSlots


SIMPLE_TYPES = {"COUNT", "DATE", "STATUS", "SIMPLE_LIST", "RELATIONSHIP", "CONCEPT"}


@dataclass(frozen=True)
class ConciseRewriteEligibility:
    eligible: bool
    answer_type: str
    risk: str
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "answer_type": self.answer_type,
            "risk": self.risk,
            "reason_codes": list(self.reason_codes),
        }


def decide_concise_rewrite_eligibility(
    *,
    prompt: str,
    legacy_answer: str,
    slots: AnswerSlots,
    evidence_bus: Any | None = None,
    evidence_quality: Any | None = None,
) -> ConciseRewriteEligibility:
    reasons: list[str] = []
    answer_type = _infer_answer_type(prompt, slots)
    risk = "LOW"

    if not legacy_answer.strip():
        return ConciseRewriteEligibility(False, answer_type, "HIGH", ["EMPTY_LEGACY_ANSWER"])

    if _has_sensitive_caveat(slots, evidence_quality):
        reasons.append("CAVEAT_SENSITIVE")
        risk = "HIGH"

    if _has_evidence_conflict(slots, evidence_quality):
        reasons.append("EVIDENCE_CONFLICT")
        risk = "HIGH"

    if answer_type == "UNKNOWN" or answer_type not in SIMPLE_TYPES:
        reasons.append("UNKNOWN_INTENT")
        risk = "MEDIUM" if risk == "LOW" else risk

    if _is_complex_multi_field_list(prompt, slots):
        reasons.append("COMPLEX_MULTI_FIELD_LIST")
        risk = "HIGH"

    if answer_type != "CONCEPT" and not _has_exact_facts(answer_type, slots, evidence_bus):
        reasons.append("MISSING_ANSWER_SLOTS")
        risk = "MEDIUM" if risk == "LOW" else risk

    if _legacy_already_concise(prompt, legacy_answer, answer_type, slots):
        reasons.append("LEGACY_ALREADY_CONCISE")

    if reasons and any(
        code in reasons
        for code in (
            "CAVEAT_SENSITIVE",
            "EVIDENCE_CONFLICT",
            "COMPLEX_MULTI_FIELD_LIST",
            "MISSING_ANSWER_SLOTS",
            "LEGACY_ALREADY_CONCISE",
            "UNKNOWN_INTENT",
        )
    ):
        return ConciseRewriteEligibility(False, answer_type, risk, reasons)

    eligible_code = {
        "COUNT": "ELIGIBLE_COUNT_EXACT_FACTS",
        "DATE": "ELIGIBLE_DATE_EXACT_FACTS",
        "STATUS": "ELIGIBLE_STATUS_EXACT_FACTS",
        "SIMPLE_LIST": "ELIGIBLE_SIMPLE_LIST",
        "RELATIONSHIP": "ELIGIBLE_RELATIONSHIP_EXACT_FACTS",
        "CONCEPT": "ELIGIBLE_SIMPLE_CONCEPT",
    }.get(answer_type, "UNKNOWN_INTENT")
    reasons.append(eligible_code)
    return ConciseRewriteEligibility(True, answer_type, risk, reasons)


def _infer_answer_type(prompt: str, slots: AnswerSlots) -> str:
    text = _norm(prompt)
    if re.search(r"\b(what is|why|how does|explain|define|compare)\b", text) and not re.search(
        r"\b(how many|count|number of|total|list|show|give me|status|state|when|date)\b",
        text,
    ):
        return "CONCEPT"
    if re.search(r"\b(when|date|created|updated|published|timestamp)\b", text) or slots.timestamps:
        return "DATE"
    if re.search(r"\b(list|show|give me|which|what are)\b", text) and (slots.entity_names or slots.entity_ids):
        return "SIMPLE_LIST"
    if re.search(r"\b(status|state|active|inactive|failed|succeeded|published)\b", text) or slots.statuses:
        return "STATUS"
    if re.search(r"\b(how many|count|number of|total)\b", text) or slots.counts:
        return "COUNT"
    if re.search(r"\b(associated|mapped|connected|relationship|belongs to)\b", text):
        return "RELATIONSHIP"
    return "UNKNOWN"


def _has_exact_facts(answer_type: str, slots: AnswerSlots, evidence_bus: Any | None) -> bool:
    if answer_type == "COUNT":
        return bool(slots.counts or getattr(evidence_bus, "counts", None) or getattr(evidence_bus, "api_counts", None))
    if answer_type == "DATE":
        return bool(slots.timestamps or getattr(evidence_bus, "timestamps", None) or getattr(evidence_bus, "api_timestamps", None))
    if answer_type == "STATUS":
        return bool(slots.statuses or getattr(evidence_bus, "statuses", None) or getattr(evidence_bus, "api_statuses", None))
    if answer_type == "SIMPLE_LIST":
        return bool(slots.entity_names or slots.entity_ids or getattr(evidence_bus, "names", None) or getattr(evidence_bus, "api_names", None))
    if answer_type == "RELATIONSHIP":
        return bool(slots.entity_names and (slots.entity_ids or slots.first_rows or slots.api_items))
    return True


def _has_sensitive_caveat(slots: AnswerSlots, evidence_quality: Any | None) -> bool:
    non_dry_run_errors = [str(error) for error in slots.api_errors if str(error).lower() != "dry_run"]
    if slots.api_error or non_dry_run_errors or slots.discrepancy:
        return True
    state = (slots.api_evidence_state or "").lower()
    if state in {"api_error", "malformed_response", "live_empty"}:
        return True
    quality_text = str(evidence_quality or "").lower()
    if slots.dry_run and not slots.api_error and "sql_direct_answer" in quality_text and "sql_success_api_error" in quality_text:
        return False
    return any(token in quality_text for token in ("api_error", "live_empty", "unresolved_param", "conflict"))


def _has_evidence_conflict(slots: AnswerSlots, evidence_quality: Any | None) -> bool:
    if slots.discrepancy:
        return True
    quality_text = str(evidence_quality or "").lower()
    if slots.dry_run and not slots.api_error and "sql_success_api_error" in quality_text:
        return False
    return "conflict" in quality_text or "mismatch" in quality_text


def _is_complex_multi_field_list(prompt: str, slots: AnswerSlots) -> bool:
    text = _norm(prompt)
    field_mentions = sum(
        1
        for token in ("id", "ids", "status", "state", "date", "published", "created", "updated", "name", "names")
        if re.search(rf"\b{re.escape(token)}\b", text)
    )
    if field_mentions >= 3:
        return True
    if " and " in text and "," in text and re.search(r"\b(list|show|give me)\b", text):
        return True
    if len(slots.entity_names) > 8 or len(slots.entity_ids) > 8:
        return True
    if slots.entity_names and slots.entity_ids and slots.statuses and slots.timestamps:
        return True
    return False


def _legacy_already_concise(prompt: str, legacy_answer: str, answer_type: str, slots: AnswerSlots) -> bool:
    text = legacy_answer.strip()
    lowered = text.lower()
    if lowered.startswith(("the local snapshot contains", "based on", "the sql evidence", "the database shows")):
        return False
    if "schema records" in lowered and "schemas" in prompt.lower():
        return False
    words = re.findall(r"\w+", text)
    if len(words) > 8:
        return False
    if answer_type == "COUNT" and slots.counts and any(str(value) in text for value in slots.counts):
        return True
    if answer_type == "DATE" and slots.timestamps and any(_date_token(value) in text for value in slots.timestamps):
        return True
    if answer_type == "STATUS" and slots.statuses and any(str(value).lower() in text.lower() for value in slots.statuses):
        return True
    if answer_type == "SIMPLE_LIST" and slots.entity_names and all(name.lower() in text.lower() for name in slots.entity_names[:3]):
        return True
    return False


def _date_token(value: Any) -> str:
    return str(value)[:10]


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
