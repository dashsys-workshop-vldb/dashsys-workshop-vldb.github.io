from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots


ANSWER_INTENTS = {"CONCEPT", "COUNT", "LIST", "STATUS", "DATE", "RELATIONSHIP", "MIXED", "ERROR_CAVEAT", "UNKNOWN"}
ANSWER_MODES = {"CANONICAL_DATA", "LLM_CONCEPT", "HYBRID_MIXED", "CANONICAL_CAVEAT", "LEGACY_FALLBACK"}


@dataclass(frozen=True)
class AnswerIntentDecision:
    answer_intent: str
    answer_mode: str
    confidence: str = "LOW"
    reason_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        intent = str(self.answer_intent or "UNKNOWN").upper()
        mode = str(self.answer_mode or "LEGACY_FALLBACK").upper()
        confidence = str(self.confidence or "LOW").upper()
        object.__setattr__(self, "answer_intent", intent if intent in ANSWER_INTENTS else "UNKNOWN")
        object.__setattr__(self, "answer_mode", mode if mode in ANSWER_MODES else "LEGACY_FALLBACK")
        object.__setattr__(self, "confidence", confidence if confidence in {"HIGH", "MEDIUM", "LOW"} else "LOW")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def route_answer_intent(
    prompt: str,
    *,
    semantic_parse: Any | None = None,
    objective_features: Any | None = None,
    evidence_bus: Any | None = None,
    slots: AnswerSlots | None = None,
    evidence_quality: dict[str, Any] | None = None,
    caveat_states: list[str] | None = None,
) -> AnswerIntentDecision:
    del semantic_parse, objective_features, evidence_bus
    text = _norm(prompt)
    quality = evidence_quality or {}
    api_codes = {str(value).upper() for value in quality.get("api", []) if value}
    sql_codes = {str(value).upper() for value in quality.get("sql", []) if value}
    caveat_codes = {str(value).upper() for value in caveat_states or [] if value}
    reason_codes: list[str] = []

    primary_caveat = _primary_caveat(slots, api_codes, sql_codes, caveat_codes)
    data_intents = _data_intents(text, slots)
    concept = _has_conceptual_request(text)
    if concept:
        reason_codes.append("CONCEPT_CUE")
    if data_intents:
        reason_codes.append("STRUCTURED_DATA_ROLE")
    if primary_caveat:
        reason_codes.append("PRIMARY_CAVEAT_STATE")

    if primary_caveat and not _has_answerable_structured_fact(slots):
        return AnswerIntentDecision("ERROR_CAVEAT", "CANONICAL_CAVEAT", "HIGH", reason_codes)
    if concept and data_intents:
        return AnswerIntentDecision("MIXED", "HYBRID_MIXED", "HIGH", reason_codes)
    if data_intents:
        intent = _priority_data_intent(data_intents, text)
        return AnswerIntentDecision(intent, "CANONICAL_DATA", "HIGH", reason_codes)
    if concept and not _instance_lookup_cue(text, slots):
        return AnswerIntentDecision("CONCEPT", "LLM_CONCEPT", "HIGH", reason_codes)
    if primary_caveat:
        return AnswerIntentDecision("ERROR_CAVEAT", "CANONICAL_CAVEAT", "MEDIUM", reason_codes)
    return AnswerIntentDecision("UNKNOWN", "LEGACY_FALLBACK", "LOW", reason_codes or ["UNKNOWN_INTENT"])


def _data_intents(text: str, slots: AnswerSlots | None) -> list[str]:
    intents: list[str] = []
    if re.search(r"\b(how many|count|counts|total|number of)\b", text) and _has_counts(slots):
        intents.append("COUNT")
    if re.search(r"\b(when|created|updated|modified|published|deployed|timestamp|date|recent|latest)\b", text) and _has_dates(slots):
        intents.append("DATE")
    if re.search(r"\b(status|state|active|inactive|failed|succeeded|published|draft|deployed)\b", text) and _has_status_or_rows(slots):
        intents.append("STATUS")
    if re.search(r"\b(associated|connected|linked|relationship|maps? to|belongs to|used by|uses)\b", text) and _has_names_or_ids(slots):
        intents.append("RELATIONSHIP")
    if re.search(r"\b(list|show|return|give me|which|what are|display|find)\b", text) and _has_names_or_ids(slots):
        intents.append("LIST")
    return _dedupe(intents)


def _priority_data_intent(intents: list[str], text: str) -> str:
    if "COUNT" in intents:
        return "COUNT"
    if "STATUS" in intents and re.search(r"\b(status|state|active|inactive|failed|succeeded|published|draft|deployed)\b", text):
        return "STATUS"
    if "LIST" in intents and re.search(r"\b(list|show|return|give me|which|display|export|all columns|including)\b", text):
        return "LIST"
    for intent in ["DATE", "RELATIONSHIP", "STATUS", "LIST"]:
        if intent in intents:
            return intent
    return intents[0] if intents else "UNKNOWN"


def _has_conceptual_request(text: str) -> bool:
    if re.search(r"\b(what is|what does|define|definition|meaning|explain|why|how does|how do|compare|benefits?|reasons?|examples?|overview)\b", text):
        return True
    if " in the phrase " in text or " word " in text:
        return True
    return False


def _instance_lookup_cue(text: str, slots: AnswerSlots | None) -> bool:
    if re.search(r"\b(current|live|sandbox|platform|records?|show|list|lookup|find|status|count)\b", text) and _has_answerable_structured_fact(slots):
        return True
    return False


def _primary_caveat(
    slots: AnswerSlots | None,
    api_codes: set[str],
    sql_codes: set[str],
    caveat_codes: set[str],
) -> bool:
    if "API_ERROR" in api_codes or "API_ERROR" in caveat_codes:
        return True
    if "API_LIVE_EMPTY" in api_codes or "LIVE_EMPTY" in caveat_codes:
        return True
    if "UNRESOLVED_PARAM_BLOCKED" in api_codes or "UNRESOLVED_PARAM_BLOCKED" in caveat_codes:
        return True
    if "SQL_ZERO_ROWS" in sql_codes and not _has_answerable_structured_fact(slots):
        return True
    if slots is None:
        return False
    if slots.api_error or str(slots.answer_slot_source or "").lower() == "api_error":
        return True
    return "empty" in str(slots.api_evidence_state or "").lower()


def _has_counts(slots: AnswerSlots | None) -> bool:
    return bool(slots and (slots.counts or slots.sql_row_count is not None or slots.api_item_count is not None))


def _has_dates(slots: AnswerSlots | None) -> bool:
    return bool(slots and slots.timestamps)


def _has_status_or_rows(slots: AnswerSlots | None) -> bool:
    return bool(slots and (slots.statuses or slots.first_rows or slots.important_rows or slots.api_items or slots.important_items))


def _has_names_or_ids(slots: AnswerSlots | None) -> bool:
    return bool(slots and (slots.entity_names or slots.entity_ids or slots.first_rows or slots.important_rows or slots.api_items or slots.important_items))


def _has_answerable_structured_fact(slots: AnswerSlots | None) -> bool:
    return _has_counts(slots) or _has_names_or_ids(slots) or _has_dates(slots) or bool(slots and slots.statuses)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
