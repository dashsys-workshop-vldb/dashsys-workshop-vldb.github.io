from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .answer_intent import AnswerIntent, classify_answer_intent
from .answer_slots import AnswerSlots, extract_answer_slots
from .answer_verifier import family_noun, pluralize


@dataclass(frozen=True)
class EvidenceAwareTemplateResult:
    answer: str
    template_id: str
    evidence_source: str
    evidence_state: str | None
    used_fields: list[str] = field(default_factory=list)
    required_caveat_present: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "template_id": self.template_id,
            "evidence_source": self.evidence_source,
            "evidence_state": self.evidence_state,
            "used_fields": self.used_fields,
            "required_caveat_present": self.required_caveat_present,
            "notes": self.notes,
        }


def compose_evidence_aware_answer(
    query: str,
    tool_results: list[dict[str, Any]],
    *,
    variant: str = "evidence_source_aware_templates",
    baseline_answer: str | None = None,
    api_required: bool = False,
) -> EvidenceAwareTemplateResult:
    slots = extract_answer_slots(query, tool_results)
    intent = classify_answer_intent(query, slots)
    family = _family_from_results(tool_results) or slots.answer_family
    noun = family_noun(family)
    plural = pluralize(noun)
    facts = collect_answer_evidence(tool_results, slots)
    dry_note = "Live API verification was unavailable because credentials were not provided."

    if slots.discrepancy:
        sql_count = slots.sql_row_count if slots.sql_row_count is not None else "unknown"
        api_count = slots.api_item_count if slots.api_item_count is not None else "unknown"
        return _result(
            f"SQL and API evidence disagree: SQL returned {sql_count}, while live API returned {api_count}.",
            "sql_api_mismatch",
            "mixed",
            slots,
            ["sql_count", "api_count"],
        )

    if slots.api_evidence_state == "malformed_response":
        return _result(
            "The API response could not be parsed, so live API evidence could not be used.",
            "malformed_response",
            "api_error",
            slots,
            ["api_errors"],
        )

    if slots.api_error and not slots.dry_run:
        detail = f" {slots.api_errors[0]}" if slots.api_errors else ""
        return _result(
            f"The API request failed, so live API evidence could not be used.{detail}",
            "api_error",
            "api_error",
            slots,
            ["api_errors"],
        )

    if slots.answer_slot_source == "live_api" and slots.api_evidence_state in {"live_empty", "live_empty_result"}:
        if intent == AnswerIntent.COUNT:
            answer = f"Live API returned 0 matching {plural}."
        else:
            answer = f"Live API returned no matching {plural}."
        return _result(answer, "live_empty", "live_api", slots, ["api_item_count"])

    direct = _direct_answer_from_facts(intent, noun, plural, facts, variant)
    if direct:
        answer, used = direct
        source = "live_api" if facts["api_values_present"] else "sql"
        if slots.dry_run:
            if _variant_minimal_caveat(variant):
                answer = f"{answer} {dry_note}"
            elif api_required or variant != "conservative_rewrite_only":
                answer = f"{answer} {dry_note}"
        return _result(answer, f"{variant}_{intent.value.lower()}", source, slots, used, api_required=api_required)

    if slots.dry_run:
        if intent == AnswerIntent.COUNT:
            answer = f"The {noun} count cannot be determined from the available evidence. {dry_note}"
        elif intent == AnswerIntent.LIST:
            answer = f"The requested {noun} list requires live API evidence. {dry_note}"
        elif intent == AnswerIntent.STATUS:
            answer = f"The requested {noun} status requires live API evidence. {dry_note}"
        elif intent == AnswerIntent.WHEN:
            answer = f"The requested {noun} timestamp requires live API evidence. {dry_note}"
        else:
            answer = f"The requested {noun} details require live API evidence. {dry_note}"
        return _result(answer, "dry_run_unavailable", "dry_run_unavailable", slots, ["dry_run"], api_required=api_required)

    if slots.sql_row_count == 0:
        return _result(f"The SQL query returned no matching {plural}.", "sql_empty", "sql", slots, ["sql_row_count"])

    fallback = baseline_answer or f"The requested {noun} answer could not be determined from the available evidence."
    return _result(fallback, "fallback_baseline_or_unavailable", "unknown", slots, [], api_required=api_required)


def collect_answer_evidence(tool_results: list[dict[str, Any]], slots: AnswerSlots) -> dict[str, Any]:
    counts: list[Any] = []
    names: list[str] = list(slots.entity_names)
    ids: list[str] = list(slots.entity_ids)
    statuses: list[str] = list(slots.statuses)
    timestamps: list[str] = list(slots.timestamps)
    api_values_present = bool(slots.api_items or slots.live_api_evidence_available)
    sql_values_present = bool(slots.first_rows or slots.sql_row_count is not None)

    for result in tool_results:
        payload = result.get("payload") or {}
        if result.get("type") == "sql":
            for row in _rows(payload):
                counts.extend(_count_values(row))
        elif result.get("type") == "api":
            parsed = payload.get("parsed_evidence") if isinstance(payload, dict) else None
            if isinstance(parsed, dict):
                counts.extend((parsed.get("counts") or {}).values() if isinstance(parsed.get("counts"), dict) else [])
                names.extend(str(value) for value in parsed.get("names", []) if value not in (None, ""))
                ids.extend(str(value) for value in parsed.get("ids", []) if value not in (None, ""))
                statuses.extend(str(value) for value in parsed.get("statuses", []) if value not in (None, ""))
                ts = parsed.get("timestamps")
                if isinstance(ts, dict):
                    timestamps.extend(str(value) for value in ts.values() if value not in (None, ""))

    if not counts:
        counts = list(slots.counts)
    return {
        "counts": _dedupe_values(counts),
        "names": _dedupe_text(names),
        "ids": _dedupe_text(ids),
        "statuses": _dedupe_text(statuses),
        "timestamps": _dedupe_text(timestamps),
        "api_values_present": api_values_present,
        "sql_values_present": sql_values_present,
    }


def _direct_answer_from_facts(
    intent: AnswerIntent,
    noun: str,
    plural: str,
    facts: dict[str, Any],
    variant: str,
) -> tuple[str, list[str]] | None:
    counts = facts["counts"]
    names = facts["names"]
    ids = facts["ids"]
    statuses = facts["statuses"]
    timestamps = facts["timestamps"]
    if intent == AnswerIntent.COUNT and counts:
        return (f"You have {counts[0]} {plural}.", ["counts"])
    if intent == AnswerIntent.LIST:
        values = names[:5] or ids[:5]
        if values:
            label = plural if variant != "direct_first_templates" else "matches"
            return (f"Matching {label}: {', '.join(str(value) for value in values)}.", ["names" if names else "ids"])
    if intent == AnswerIntent.STATUS and statuses:
        subject = (names or ids or [f"the {noun}"])[0]
        return (f"{subject} is {statuses[0]}.", ["statuses"])
    if intent == AnswerIntent.WHEN and timestamps:
        subject = (names or ids or [f"the {noun}"])[0]
        return (f"{subject} was recorded at {timestamps[0]}.", ["timestamps"])
    if intent == AnswerIntent.YES_NO:
        if statuses:
            subject = (names or ids or [f"the {noun}"])[0]
            return (f"Yes, {subject} has status {statuses[0]}.", ["statuses"])
        if names or ids or counts:
            return (f"Yes, matching {plural} were found.", ["names" if names else "ids" if ids else "counts"])
    if intent == AnswerIntent.DETAIL:
        values = names[:3] or ids[:3]
        if values:
            return (f"Matching {plural}: {', '.join(str(value) for value in values)}.", ["names" if names else "ids"])
    return None


def _result(
    answer: str,
    template_id: str,
    evidence_source: str,
    slots: AnswerSlots,
    used_fields: list[str],
    *,
    api_required: bool = False,
) -> EvidenceAwareTemplateResult:
    required = not (api_required and slots.dry_run) or "verification was unavailable" in answer.lower()
    return EvidenceAwareTemplateResult(
        answer=" ".join(answer.split()),
        template_id=template_id,
        evidence_source=evidence_source,
        evidence_state=slots.api_evidence_state,
        used_fields=used_fields,
        required_caveat_present=required,
    )


def _variant_minimal_caveat(variant: str) -> bool:
    return variant in {"dry_run_minimal_caveat", "direct_first_templates", "intent_specific_templates", "evidence_source_aware_templates"}


def _family_from_results(tool_results: list[dict[str, Any]]) -> str | None:
    for result in tool_results:
        step = result.get("step") or {}
        family = step.get("family")
        if family:
            return str(family)
    return None


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _count_values(row: dict[str, Any]) -> list[Any]:
    values = []
    for key, value in row.items():
        key_norm = str(key).lower()
        if value in (None, "", [], {}):
            continue
        if any(part in key_norm for part in ["count", "total", "number"]):
            values.append(value)
    if not values and len(row) == 1:
        value = next(iter(row.values()))
        if isinstance(value, (int, float)) or str(value).isdigit():
            values.append(value)
    return values


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = str(value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            output.append(str(value))
    return output


def _dedupe_values(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for value in values:
        key = str(value)
        if key and key not in seen:
            seen.add(key)
            output.append(value)
    return output
