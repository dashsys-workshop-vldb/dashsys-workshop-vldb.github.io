from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_claims import AnswerClaim, extract_claims
from .answer_intent import AnswerIntent
from .answer_slots import AnswerSlots, normalize_text


@dataclass
class VerificationResult:
    ok: bool
    unsupported_claims: list[AnswerClaim] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def unsupported_count(self) -> int:
        return len(self.unsupported_claims)

    def compact(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "unsupported_claims_count": self.unsupported_count,
            "errors": self.errors[:3],
            "warnings": self.warnings[:3],
        }


def verify_answer(answer: str, slots: AnswerSlots) -> VerificationResult:
    claims = extract_claims(answer)
    unsupported: list[AnswerClaim] = []
    errors: list[str] = []
    warnings: list[str] = []
    query_norm = normalize_text(slots.query)

    for claim in claims:
        if claim.claim_type == "number" and not number_supported(claim.value, slots, query_norm):
            unsupported.append(claim)
            errors.append(f"unsupported_number:{claim.value}")
        elif claim.claim_type == "timestamp" and not text_supported(claim.value, slots, query_norm, timestamp=True):
            unsupported.append(claim)
            errors.append(f"unsupported_timestamp:{claim.value}")
        elif claim.claim_type == "entity" and not text_supported(claim.value, slots, query_norm):
            unsupported.append(claim)
            errors.append(f"unsupported_entity:{claim.value}")
        elif claim.claim_type == "status" and not status_supported(claim.value, slots, query_norm):
            unsupported.append(claim)
            errors.append(f"unsupported_status:{claim.value}")
        elif claim.claim_type == "api_confirmation" and slots.dry_run and not slots.api_items:
            unsupported.append(claim)
            errors.append("api_confirmation_without_live_api")

    if slots.discrepancy and not any(claim.claim_type == "discrepancy" for claim in claims):
        errors.append("missing_sql_api_discrepancy")

    # If all evidence is absent, explicit facts should come only from the query itself.
    if not slots.first_rows and not slots.api_items and not slots.counts:
        fact_claims = [claim for claim in claims if claim.claim_type in {"number", "timestamp", "entity", "status"}]
        if fact_claims:
            warnings.append("answer_contains_only_query_supported_facts")

    return VerificationResult(ok=not errors, unsupported_claims=unsupported, errors=list(dict.fromkeys(errors)), warnings=warnings)


def number_supported(value: str, slots: AnswerSlots, query_norm: str) -> bool:
    stripped = value.replace(",", "")
    if stripped in slots.evidence_numbers:
        return True
    if stripped in {re.sub(r"[^\d.]", "", str(item)) for item in slots.counts}:
        return True
    if slots.sql_row_count is not None and stripped == str(slots.sql_row_count):
        return True
    if slots.api_item_count is not None and stripped == str(slots.api_item_count):
        return True
    return bool(re.search(rf"(?<!\d){re.escape(stripped)}(?!\d)", query_norm))


def text_supported(value: str, slots: AnswerSlots, query_norm: str, *, timestamp: bool = False) -> bool:
    value_norm = normalize_text(value)
    if not value_norm:
        return True
    if value_norm in query_norm:
        return True
    if any(value_norm in evidence or evidence in value_norm for evidence in slots.evidence_strings):
        return True
    if timestamp:
        date = value_norm[:10]
        return any(date and date in normalize_text(item) for item in slots.timestamps)
    return False


def status_supported(value: str, slots: AnswerSlots, query_norm: str) -> bool:
    value_norm = normalize_text(value)
    if value_norm in query_norm:
        return True
    return any(value_norm == normalize_text(status) for status in slots.statuses)


def safe_rewrite(query: str, slots: AnswerSlots, intent: AnswerIntent, family: str) -> str:
    if slots.discrepancy:
        return discrepancy_answer(slots)
    if slots.first_rows:
        row_answer = answer_from_rows(slots, intent)
        if row_answer:
            return row_answer
    if slots.api_items:
        api_answer = answer_from_api_items(slots, intent)
        if api_answer:
            return api_answer
    return unavailable_answer(query, slots, intent, family)


def discrepancy_answer(slots: AnswerSlots) -> str:
    sql_count = slots.sql_row_count if slots.sql_row_count is not None else "unknown"
    api_count = slots.api_item_count if slots.api_item_count is not None else "unknown"
    return f"The SQL and API evidence disagree: SQL returned {sql_count} row(s), while live API evidence returned {api_count} item(s)."


def answer_from_rows(slots: AnswerSlots, intent: AnswerIntent) -> str | None:
    names = slots.entity_names[:5]
    ids = slots.entity_ids[:5]
    count = slots.sql_row_count if slots.sql_row_count is not None else len(slots.first_rows)
    if intent == AnswerIntent.COUNT:
        return f"The database count is {count}."
    if intent == AnswerIntent.WHEN and slots.timestamps:
        subject = names[0] if names else "the matching record"
        return f"{subject} has timestamp {slots.timestamps[0]} in the SQL evidence."
    if intent == AnswerIntent.STATUS and slots.statuses:
        subject = names[0] if names else "the matching record"
        return f"{subject} has status/state {slots.statuses[0]} in the SQL evidence."
    if names:
        return f"Based on the SQL evidence, the matching item(s) are: {', '.join(names)}."
    if ids:
        return f"Based on the SQL evidence, the matching ID(s) are: {', '.join(ids)}."
    return None


def answer_from_api_items(slots: AnswerSlots, intent: AnswerIntent) -> str | None:
    count = slots.api_item_count if slots.api_item_count is not None else len(slots.api_items)
    names = slots.entity_names[:5]
    ids = slots.entity_ids[:5]
    if intent == AnswerIntent.COUNT:
        return f"The API evidence reports {count} item(s)."
    if intent == AnswerIntent.STATUS and slots.statuses:
        return f"The API evidence reports status/state {slots.statuses[0]}."
    if names:
        return f"Based on live API evidence, the matching item(s) are: {', '.join(names)}."
    if ids:
        return f"Based on live API evidence, the matching ID(s) are: {', '.join(ids)}."
    return f"Live API evidence returned {count} item(s)."


def unavailable_answer(query: str, slots: AnswerSlots, intent: AnswerIntent, family: str) -> str:
    noun = family_noun(family)
    live_note = "Live API verification was not executed because Adobe credentials are unavailable."
    if slots.api_error and not slots.dry_run:
        live_note = "API evidence did not provide usable data."
    if intent == AnswerIntent.COUNT:
        return f"The {noun} count cannot be determined from the available evidence. {live_note}"
    if intent == AnswerIntent.LIST:
        return f"The requested {noun} list requires live API evidence. {live_note}"
    if intent == AnswerIntent.WHEN:
        metric = f" for {slots.metrics[0]}" if slots.metrics else ""
        window = ""
        if len(slots.date_ranges) >= 2:
            window = f" between {slots.date_ranges[0]} and {slots.date_ranges[-1]}"
        return f"The requested timestamp or daily value{metric}{window} requires live API evidence. {live_note}"
    if intent == AnswerIntent.STATUS:
        return f"The requested {noun} status requires live API evidence. {live_note}"
    if intent == AnswerIntent.YES_NO:
        return f"No supported yes/no answer can be determined from the available evidence. {live_note}"
    return f"The requested {noun} details require live API evidence. {live_note}"


def family_noun(family: str) -> str:
    mapping = {
        "observability_metrics": "observability metric",
        "segment_definitions": "segment definition",
        "segment_jobs": "segment evaluation job",
        "tags": "tag",
        "batch": "batch",
        "merge_policy": "merge policy",
        "audit_destination_mapping": "audit event",
        "audit_entity_created": "audit event",
        "segment_destination": "segment-destination relationship",
        "property_field": "field/property",
        "failed_dataflow_runs": "failed dataflow run",
    }
    return mapping.get(family, family.replace("_", " "))
