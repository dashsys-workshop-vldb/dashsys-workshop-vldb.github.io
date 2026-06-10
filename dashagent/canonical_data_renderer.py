from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_intent_router import AnswerIntentDecision
from .answer_slots import AnswerSlots


@dataclass(frozen=True)
class CanonicalAnswer:
    answer: str
    rendered_roles: list[str] = field(default_factory=list)
    caveat_roles: list[str] = field(default_factory=list)
    source_facts: dict[str, Any] = field(default_factory=dict)
    missing_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_canonical_data_answer(
    prompt: str,
    intent: AnswerIntentDecision | str,
    slots: AnswerSlots,
    *,
    evidence_quality: dict[str, Any] | None = None,
    evidence_bus: Any | None = None,
) -> CanonicalAnswer:
    del evidence_bus
    answer_intent = intent.answer_intent if isinstance(intent, AnswerIntentDecision) else str(intent or "UNKNOWN").upper()
    quality = evidence_quality or {}
    caveats = _canonical_caveats(slots, quality)
    if answer_intent == "ERROR_CAVEAT":
        return _render_caveat(slots, quality)
    if answer_intent == "COUNT":
        return _render_count(prompt, slots, caveats)
    if answer_intent == "DATE":
        return _render_date(prompt, slots, caveats)
    if answer_intent == "STATUS":
        return _render_status(prompt, slots, caveats)
    if answer_intent == "RELATIONSHIP":
        return _render_relationship(prompt, slots, caveats)
    if answer_intent == "LIST":
        return _render_list(prompt, slots, caveats)
    return CanonicalAnswer("", missing_roles=["UNKNOWN_INTENT"])


def _render_count(prompt: str, slots: AnswerSlots, caveats: list[str]) -> CanonicalAnswer:
    count = _first_count(slots)
    if count is None:
        return CanonicalAnswer("", missing_roles=["COUNT"])
    label = _object_label(prompt, plural=True)
    if _local_scope(prompt):
        answer = f"There are {count} {label} in the local snapshot."
        roles = ["COUNT", "SCOPE"]
    elif caveats and (_live_scope(prompt) or slots.api_error or slots.dry_run):
        answer = f"Local snapshot {label} count: {count}. {' '.join(caveats)}"
        roles = ["COUNT", "SCOPE", "CAVEAT"]
    else:
        answer = f"There are {count} {label}."
        roles = ["COUNT"]
    return CanonicalAnswer(answer, roles, _caveat_roles(caveats), {"count": str(count), "object_label": label})


def _render_date(prompt: str, slots: AnswerSlots, caveats: list[str]) -> CanonicalAnswer:
    if not slots.timestamps:
        return CanonicalAnswer("", missing_roles=["DATE"])
    entity = _first_entity(slots) or _object_label(prompt, plural=False).rstrip("s")
    field = _date_field_label(prompt)
    date = _date_only(slots.timestamps[0])
    answer = f"{entity} was {field} on {date}."
    if caveats:
        answer = f"{answer} {' '.join(caveats)}"
    return CanonicalAnswer(answer, ["ENTITY", "DATE"], _caveat_roles(caveats), {"entity": entity, "date": date, "field": field})


def _render_status(prompt: str, slots: AnswerSlots, caveats: list[str]) -> CanonicalAnswer:
    rows = _rows(slots)
    if rows:
        pairs = []
        for row in rows[:5]:
            name = _row_name(row) or _row_id(row)
            status = _row_status(row)
            if name and status:
                pairs.append(f"{name} ({status})")
        if pairs:
            label = _object_label(prompt, plural=True).capitalize()
            answer = f"{label}: {'; '.join(pairs)}."
            if len(pairs) == 1:
                name, status = pairs[0].rsplit(" (", 1)
                answer = f"{name} is {status.rstrip(')')}."
            if caveats:
                answer = f"{answer} {' '.join(caveats)}"
            return CanonicalAnswer(answer, ["ENTITY", "STATUS"], _caveat_roles(caveats), {"items": pairs})
    if slots.entity_names and slots.statuses:
        if len(slots.entity_names) == 1 and len(slots.statuses) == 1:
            answer = f"{slots.entity_names[0]} is {slots.statuses[0]}."
        else:
            pairs = [f"{name} ({status})" for name, status in zip(slots.entity_names, slots.statuses)]
            answer = f"{_object_label(prompt, plural=True).capitalize()}: {'; '.join(pairs)}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return CanonicalAnswer(answer, ["ENTITY", "STATUS"], _caveat_roles(caveats), {"names": slots.entity_names[:5], "statuses": slots.statuses[:5]})
    return CanonicalAnswer("", missing_roles=["STATUS"])


def _render_list(prompt: str, slots: AnswerSlots, caveats: list[str]) -> CanonicalAnswer:
    rows = _rows(slots)
    items = _row_items(rows, prompt=prompt) if rows else _dedupe([*slots.entity_names, *slots.entity_ids])[:5]
    if not items:
        if _live_empty(slots, {}):
            return CanonicalAnswer("No matching records were returned for this query/scope.", ["CAVEAT"], ["LIVE_EMPTY"], {})
        return CanonicalAnswer("", missing_roles=["LIST"])
    label = _object_label(prompt, plural=True).capitalize()
    answer = f"{label}: {'; '.join(items)}."
    if caveats:
        answer = f"{answer} {' '.join(caveats)}"
    return CanonicalAnswer(answer, ["LIST"], _caveat_roles(caveats), {"items": items})


def _render_relationship(prompt: str, slots: AnswerSlots, caveats: list[str]) -> CanonicalAnswer:
    rows = _rows(slots)
    if rows:
        return _render_list(prompt, slots, caveats)
    if len(slots.entity_names) >= 2:
        answer = f"{slots.entity_names[0]} is associated with {slots.entity_names[1]}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return CanonicalAnswer(answer, ["RELATIONSHIP"], _caveat_roles(caveats), {"subject": slots.entity_names[0], "object": slots.entity_names[1]})
    return CanonicalAnswer("", missing_roles=["RELATIONSHIP"])


def _render_caveat(slots: AnswerSlots, quality: dict[str, Any]) -> CanonicalAnswer:
    if _api_error(slots, quality):
        return CanonicalAnswer("API unavailable/error; cannot verify live state.", ["CAVEAT"], ["API_ERROR"], {})
    if _unresolved_param(quality):
        return CanonicalAnswer(
            "Live API verification could not be executed safely because a required parameter was unresolved.",
            ["CAVEAT"],
            ["UNRESOLVED_PARAM_BLOCKED"],
            {},
        )
    if _live_empty(slots, quality):
        return CanonicalAnswer("No matching records were returned for this query/scope.", ["CAVEAT"], ["LIVE_EMPTY"], {})
    if "SQL_ZERO_ROWS" in {str(value).upper() for value in quality.get("sql", []) if value}:
        return CanonicalAnswer("No matching records were found in the local snapshot.", ["CAVEAT"], ["SQL_EMPTY"], {})
    return CanonicalAnswer("No matching evidence was available from the executed SQL/API tools.", ["CAVEAT"], ["MISSING_EVIDENCE"], {})


def _canonical_caveats(slots: AnswerSlots, quality: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    if _api_error(slots, quality):
        caveats.append("API unavailable/error; cannot verify live state.")
    if slots.dry_run:
        caveats.append("Live API verification was not executed because Adobe credentials are unavailable.")
    if _live_empty(slots, quality) and not _has_structured_facts(slots):
        caveats.append("No matching records were returned for this query/scope.")
    return _dedupe(caveats)


def _first_count(slots: AnswerSlots) -> str | None:
    for value in slots.counts:
        normalized = _clean_count(value)
        if normalized is not None:
            return normalized
    if slots.api_item_count is not None:
        return str(slots.api_item_count)
    if slots.sql_row_count is not None:
        return str(slots.sql_row_count)
    return None


def _clean_count(value: Any) -> str | None:
    text = str(value)
    match = re.search(r"\d+(?:\.\d+)?", text)
    return match.group(0) if match else None


def _first_entity(slots: AnswerSlots) -> str | None:
    return slots.entity_names[0] if slots.entity_names else (slots.entity_ids[0] if slots.entity_ids else None)


def _rows(slots: AnswerSlots) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*slots.important_rows, *slots.first_rows, *slots.important_items, *slots.api_items]:
        if not isinstance(row, dict):
            continue
        key = _row_id(row) or _row_name(row) or str(sorted(row.items()))
        normalized = _norm(key)
        if normalized in seen:
            continue
        seen.add(normalized)
        rows.append(row)
    return rows


def _row_items(rows: list[dict[str, Any]], *, prompt: str) -> list[str]:
    items: list[str] = []
    include_id = _asks_id_or_detail(prompt)
    for row in rows[:5]:
        name = _row_name(row) or _row_id(row)
        row_id = _row_id(row)
        status = _row_status(row)
        date = _row_date(row)
        pieces = [name] if name else []
        if include_id and row_id and row_id != name:
            pieces.append(f"id={row_id}")
        if status:
            pieces.append(f"({status})")
        if date:
            pieces.append(f"last updated {date}")
        if pieces:
            items.append(" ".join(pieces))
    return items


def _row_name(row: dict[str, Any]) -> str | None:
    for key in ("name", "title", "campaign_name", "segment_name", "displayName", "display_name", "dataset_name"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return None


def _row_id(row: dict[str, Any]) -> str | None:
    for key in ("id", "_id", "campaign_id", "segment_id", "schema_id", "audienceId", "audience_id", "dataset_id"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return None


def _row_status(row: dict[str, Any]) -> str | None:
    for key in ("status", "state", "campaign_state", "lifecycleStatus", "lifecycle_status"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return None


def _row_date(row: dict[str, Any]) -> str | None:
    for key in ("updated_time", "updatedTime", "created_time", "createdTime", "lastdeployedtime", "published_time"):
        value = row.get(key)
        if value not in (None, "", [], {}):
            return _date_only(value)
    return None


def _date_field_label(prompt: str) -> str:
    text = _norm(prompt)
    if "publish" in text or "deployed" in text:
        return "published"
    if "created" in text:
        return "created"
    if "updated" in text or "modified" in text:
        return "updated"
    return "dated"


def _date_only(value: Any) -> str:
    text = str(value)
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}", text)
    return match.group(0) if match else text


def _object_label(prompt: str, *, plural: bool) -> str:
    text = _norm(prompt)
    if "schema record" in text:
        return "schema records" if plural else "schema record"
    labels = [
        ("schema", "schema", "schemas"),
        ("dataset", "dataset", "datasets"),
        ("journey", "journey", "journeys"),
        ("campaign", "campaign", "campaigns"),
        ("audience", "audience", "audiences"),
        ("segment", "segment", "segments"),
        ("tag", "tag", "tags"),
        ("flow", "flow", "flows"),
        ("batch", "batch", "batches"),
        ("merge polic", "merge policy", "merge policies"),
    ]
    for token, singular, many in labels:
        if token in text:
            return many if plural else singular
    return "records" if plural else "record"


def _local_scope(prompt: str) -> bool:
    return "local snapshot" in _norm(prompt)


def _asks_id_or_detail(prompt: str) -> bool:
    text = _norm(prompt)
    return any(token in text for token in ("id", "ids", "identifier", "details", "all columns", "including all columns"))


def _has_structured_facts(slots: AnswerSlots) -> bool:
    return bool(slots.counts or slots.entity_names or slots.entity_ids or slots.statuses or slots.timestamps or slots.first_rows or slots.important_rows or slots.api_items or slots.important_items)


def _live_scope(prompt: str) -> bool:
    text = _norm(prompt)
    return any(token in text for token in ("current", "live", "platform", "adobe experience platform", "sandbox", "schema registry"))


def _api_error(slots: AnswerSlots, quality: dict[str, Any]) -> bool:
    api_codes = {str(value).upper() for value in quality.get("api", []) if value}
    return slots.api_error or slots.api_errors or str(slots.answer_slot_source or "").lower() == "api_error" or "API_ERROR" in api_codes


def _live_empty(slots: AnswerSlots, quality: dict[str, Any]) -> bool:
    api_codes = {str(value).upper() for value in quality.get("api", []) if value}
    return "API_LIVE_EMPTY" in api_codes or "empty" in str(slots.api_evidence_state or "").lower()


def _unresolved_param(quality: dict[str, Any]) -> bool:
    api_codes = {str(value).upper() for value in quality.get("api", []) if value}
    return "UNRESOLVED_PARAM_BLOCKED" in api_codes


def _caveat_roles(caveats: list[str]) -> list[str]:
    roles: list[str] = []
    for caveat in caveats:
        upper = caveat.upper()
        if "API" in upper and ("ERROR" in upper or "UNAVAILABLE" in upper):
            roles.append("API_ERROR")
        elif "NO MATCHING" in upper:
            roles.append("LIVE_EMPTY")
        elif "CREDENTIAL" in upper or "NOT EXECUTED" in upper:
            roles.append("DRY_RUN")
    return _dedupe(roles)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
