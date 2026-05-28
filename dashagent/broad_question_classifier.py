from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


BROAD_QUESTION_TYPES = {"CONCEPTUAL_BROAD", "DATA_BROAD", "MIXED_BROAD", "NOT_BROAD", "UNKNOWN"}


@dataclass(frozen=True)
class BroadQuestionDecision:
    broad_question_type: str = "UNKNOWN"
    confidence: str = "LOW"
    reason_codes: list[str] = field(default_factory=list)
    data_signal: bool = False
    concept_signal: bool = False
    mixed_signal: bool = False

    def __post_init__(self) -> None:
        qtype = str(self.broad_question_type or "UNKNOWN").upper()
        confidence = str(self.confidence or "LOW").upper()
        object.__setattr__(self, "broad_question_type", qtype if qtype in BROAD_QUESTION_TYPES else "UNKNOWN")
        object.__setattr__(self, "confidence", confidence if confidence in {"HIGH", "MEDIUM", "LOW"} else "LOW")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_broad_question(
    prompt: str,
    *,
    objective_features: Any | None = None,
    semantic_parse: Any | None = None,
    slots: Any | None = None,
    evidence_bus: Any | None = None,
    evidence_quality: dict[str, Any] | None = None,
) -> BroadQuestionDecision:
    del objective_features, semantic_parse, evidence_bus, evidence_quality
    text = _norm(prompt)
    if _is_meta_language_prompt(text):
        return BroadQuestionDecision(
            "CONCEPTUAL_BROAD",
            "HIGH",
            ["CONCEPT_SIGNAL", "META_LANGUAGE_CONCEPT", "BROAD_CONCEPT_LLM"],
            False,
            True,
            False,
        )
    if _is_conceptual_list_prompt(text):
        return BroadQuestionDecision(
            "CONCEPTUAL_BROAD",
            "HIGH",
            ["CONCEPT_SIGNAL", "LIST_CONCEPTUAL_REQUEST", "BROAD_CONCEPT_LLM"],
            False,
            True,
            False,
        )
    concept_signal = _concept_signal(text)
    data_signal = _data_signal(text, slots)
    mixed_signal = concept_signal and data_signal and _has_both_clauses(text)
    reason_codes: list[str] = []
    if concept_signal:
        reason_codes.append("CONCEPT_SIGNAL")
    if data_signal:
        reason_codes.append("DATA_SIGNAL")

    if mixed_signal:
        reason_codes.append("BROAD_MIXED_CONCEPT_PLUS_DATA")
        return BroadQuestionDecision("MIXED_BROAD", "HIGH", reason_codes, True, True, True)

    if data_signal and _ambiguous_data_signal(text, slots):
        reason_codes.append("AMBIGUOUS_DATA_SIGNAL_FORCE_DATA")
        return BroadQuestionDecision("DATA_BROAD", "MEDIUM", reason_codes, True, concept_signal, False)

    if data_signal and _is_broad_data_prompt(text, slots):
        reason_codes.append("BROAD_DATA_EVIDENCE_REQUIRED")
        return BroadQuestionDecision("DATA_BROAD", "HIGH", reason_codes, True, concept_signal, False)

    if concept_signal and not data_signal and _is_broad_concept_prompt(text):
        reason_codes.append("BROAD_CONCEPT_LLM")
        return BroadQuestionDecision("CONCEPTUAL_BROAD", "HIGH", reason_codes, False, True, False)

    if data_signal or concept_signal:
        return BroadQuestionDecision("NOT_BROAD", "MEDIUM", reason_codes or ["NOT_BROAD"], data_signal, concept_signal, False)
    return BroadQuestionDecision("UNKNOWN", "LOW", reason_codes or ["UNKNOWN_BROADNESS"], False, False, False)


def _concept_signal(text: str) -> bool:
    return bool(
        re.search(r"\b(what is|what does|define|definition|meaning|explain|why|how does|how do|compare|benefits?|reasons?|examples?|overview)\b", text)
        or " in the phrase " in text
        or " word " in text
    )


def _is_meta_language_prompt(text: str) -> bool:
    return " in the phrase " in text or bool(re.search(r"\bwhat does\s+['\"][^'\"]+['\"]\s+mean\b", text))


def _is_conceptual_list_prompt(text: str) -> bool:
    return bool(re.search(r"\blist\b.*\b(reasons?|benefits?|examples?|ways?|why|how)\b", text))


def _data_signal(text: str, slots: Any | None) -> bool:
    del slots
    if re.search(
        r"\b(how many|count|counts|total|number of|list|show|give me|return|display|which|status|state|active|inactive|failed|succeeded|date|created|updated|published|id|ids|name|names|recent|latest|current|live|platform|api)\b",
        text,
    ):
        return True
    return False


def _has_both_clauses(text: str) -> bool:
    return any(token in text for token in (" and ", ";", ", and ")) or bool(re.search(r"\b(explain|what is|what does)\b.*\b(list|show|give me|count|how many)\b", text))


def _is_broad_concept_prompt(text: str) -> bool:
    return bool(re.search(r"\b(what is|what does|define|definition|meaning|explain|why|how does|how do|compare|benefits?|reasons?|overview)\b", text))


def _is_broad_data_prompt(text: str, slots: Any | None) -> bool:
    if "local snapshot" in text:
        return False
    if re.search(r"\b(how many|count|counts|total|number of)\b", text):
        return not _has_specific_entity(text)
    if re.search(r"\b(recent|latest|current|live|platform)\b", text):
        return True
    if re.search(r"\b(list|show|give me|return|display|which)\b", text):
        if re.search(r"\b(active|inactive|failed|succeeded|published|draft)\b", text):
            return False
        if re.search(r"\b(recent|latest|current|all)\b", text):
            return True
        return not _slot_has_specific_entity(slots) and not _has_specific_entity(text)
    return False


def _ambiguous_data_signal(text: str, slots: Any | None) -> bool:
    if "local snapshot" in text:
        return False
    if re.search(r"\b(how many|count|counts|total|number of)\b", text):
        return False
    if re.search(r"\b(list|show|give me|return|display|which)\b", text):
        return False
    if _has_specific_entity(text):
        return False
    if not _slot_has_structured_fact(slots):
        return False
    return bool(re.search(r"\b(recent|latest|current|schemas?|datasets?|journeys?|records?|counts?)\b", text))


def _slot_has_structured_fact(slots: Any | None) -> bool:
    if slots is None:
        return False
    return bool(
        getattr(slots, "counts", None)
        or getattr(slots, "entity_names", None)
        or getattr(slots, "entity_ids", None)
        or getattr(slots, "statuses", None)
        or getattr(slots, "timestamps", None)
        or getattr(slots, "first_rows", None)
        or getattr(slots, "important_rows", None)
        or getattr(slots, "api_items", None)
        or getattr(slots, "important_items", None)
    )


def _slot_has_specific_entity(slots: Any | None) -> bool:
    if slots is None:
        return False
    return bool(getattr(slots, "entity_names", None) or getattr(slots, "entity_ids", None))


def _has_specific_entity(text: str) -> bool:
    return bool(re.search(r"'[^']+'|\"[^\"]+\"|\b(named|called|for the|with id|id )\b", text))


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())
