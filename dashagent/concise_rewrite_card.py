from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_slots import AnswerSlots
from .concise_rewrite_eligibility import ConciseRewriteEligibility


@dataclass(frozen=True)
class ConciseRewriteCard:
    task: str
    user_prompt: str
    legacy_answer: str
    answer_type: str
    exact_facts: dict[str, Any]
    allowed_terms: dict[str, Any]
    forbidden: list[str] = field(default_factory=list)
    style: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "user_prompt": self.user_prompt,
            "legacy_answer": self.legacy_answer,
            "answer_type": self.answer_type,
            "exact_facts": self.exact_facts,
            "allowed_terms": self.allowed_terms,
            "forbidden": list(self.forbidden),
            "style": dict(self.style),
        }


def build_concise_rewrite_card(
    *,
    prompt: str,
    legacy_answer: str,
    slots: AnswerSlots,
    eligibility: ConciseRewriteEligibility | None = None,
    evidence_bus: Any | None = None,
    evidence_quality: Any | None = None,
) -> ConciseRewriteCard:
    answer_type = eligibility.answer_type if eligibility is not None else _infer_answer_type_from_slots(prompt, slots)
    facts = _exact_facts(prompt, slots, evidence_bus, evidence_quality)
    allowed_terms = {
        "object_phrase_from_prompt": _object_phrase_from_prompt(prompt, answer_type),
        "entity_names": _dedupe([*slots.entity_names, *list(getattr(evidence_bus, "names", []) or [])])[:8],
        "entity_ids": _dedupe([*slots.entity_ids, *list(getattr(evidence_bus, "api_ids", []) or [])])[:8],
        "status_words": _dedupe([*slots.statuses, *list(getattr(evidence_bus, "statuses", []) or [])])[:8],
        "dates": _dedupe([str(value)[:10] for value in [*slots.timestamps, *list(getattr(evidence_bus, "timestamps", []) or [])]])[:8],
        "numbers": _dedupe([str(value) for value in [*slots.counts, *list(getattr(evidence_bus, "counts", []) or [])]])[:8],
    }
    return ConciseRewriteCard(
        task="CONCISE_STYLE_REWRITE",
        user_prompt=prompt,
        legacy_answer=legacy_answer,
        answer_type=answer_type,
        exact_facts=facts,
        allowed_terms=allowed_terms,
        forbidden=[
            "Do not add facts not in exact_facts.",
            "Do not add live/current/platform wording unless scope is LIVE.",
            "Do not turn API_ERROR into no-data.",
            "Do not turn LIVE_EMPTY into global absence.",
            "Do not add caveats unless provided.",
        ],
        style={
            "max_sentences": 1,
            "prefer_short_answer": True,
            "no_explanation_unless_prompt_asks": True,
            "use_exact_values": True,
            "use_user_object_phrase": True,
        },
    )


def _exact_facts(prompt: str, slots: AnswerSlots, evidence_bus: Any | None, evidence_quality: Any | None) -> dict[str, Any]:
    items = _dedupe([*slots.entity_names, *list(getattr(evidence_bus, "names", []) or [])])[:8]
    entity_ids = _dedupe([*slots.entity_ids, *list(getattr(evidence_bus, "api_ids", []) or [])])[:8]
    statuses = _dedupe([*slots.statuses, *list(getattr(evidence_bus, "statuses", []) or []), *list(getattr(evidence_bus, "api_statuses", []) or [])])[:8]
    dates = _dedupe([str(value)[:10] for value in [*slots.timestamps, *list(getattr(evidence_bus, "timestamps", []) or []), *list(getattr(evidence_bus, "api_timestamps", []) or [])]])[:8]
    counts = _dedupe([str(value) for value in [*slots.counts, *list(getattr(evidence_bus, "counts", []) or []), *list(getattr(evidence_bus, "api_counts", []) or [])]])[:8]
    return {
        "count": counts[0] if counts else None,
        "entity": items[0] if items else None,
        "entity_id": entity_ids[0] if entity_ids else None,
        "status": statuses[0] if statuses else None,
        "date": dates[0] if dates else None,
        "items": items,
        "ids": entity_ids,
        "statuses": statuses,
        "dates": dates,
        "scope": _scope(prompt, slots),
        "caveats": _caveats(slots, evidence_quality),
    }


def _scope(prompt: str, slots: AnswerSlots) -> str:
    text = f"{prompt} {slots.query}".lower()
    if "local snapshot" in text or "snapshot" in text:
        return "LOCAL_SNAPSHOT"
    if slots.live_api_evidence_available:
        return "LIVE"
    if any(token in text for token in ("current", "live", "platform", "adobe experience platform", "api")):
        return "LIVE"
    return "UNKNOWN"


def _caveats(slots: AnswerSlots, evidence_quality: Any | None) -> list[str]:
    caveats: list[str] = []
    if slots.api_error or slots.api_errors:
        caveats.append("API_ERROR")
    quality_text = str(evidence_quality or "").lower()
    if slots.dry_run and "api_error" in quality_text:
        caveats.append("DRY_RUN_API_UNAVAILABLE")
    if (slots.api_evidence_state or "").lower() == "live_empty":
        caveats.append("LIVE_EMPTY")
    if slots.sql_row_count == 0:
        caveats.append("SQL_EMPTY")
    return caveats


def _object_phrase_from_prompt(prompt: str, answer_type: str) -> str:
    text = re.sub(r"[?!.]", "", prompt.strip())
    lower = text.lower()
    count_match = re.search(r"\b(?:how many|count|number of|total)\s+(.+?)(?:\s+do i have|\s+are there|\s+in\b|$)", lower)
    if count_match:
        return count_match.group(1).strip()
    list_match = re.search(r"\b(?:list|show|give me)\s+(.+)$", lower)
    if list_match:
        return list_match.group(1).strip()
    status_match = re.search(r"\b(?:status of|state of)\s+(.+)$", lower)
    if status_match:
        return status_match.group(1).strip()
    if "schema" in lower:
        return "schemas"
    if "journey" in lower:
        return "journeys"
    return ""


def _infer_answer_type_from_slots(prompt: str, slots: AnswerSlots) -> str:
    text = prompt.lower()
    if slots.counts or "how many" in text or "count" in text:
        return "COUNT"
    if slots.timestamps or "when" in text or "date" in text:
        return "DATE"
    if slots.statuses or "status" in text:
        return "STATUS"
    if slots.entity_names or slots.entity_ids:
        return "SIMPLE_LIST"
    return "UNKNOWN"


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in (None, "", [], {}):
            continue
        text = str(value)
        key = text.lower()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result
