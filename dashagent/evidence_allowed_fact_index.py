from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots
from .evidence_bus import EvidenceBus


SENSITIVE_CARD_KEYS = {
    "gold",
    "gold_answer",
    "category",
    "tags",
    "oracle",
    "oracle_sql",
    "expected_trace",
    "expected_observable_trace",
    "expected_tool_calls",
}


@dataclass(frozen=True)
class AllowedFactIndex:
    counts: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    allowed_caveats: list[str] = field(default_factory=list)
    live_empty_scopes: list[str] = field(default_factory=list)
    api_error_scopes: list[str] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)
    evidence_strings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compact_allowed_facts(self, limit: int = 40) -> list[str]:
        facts: list[str] = []
        facts.extend(f"count:{value}" for value in self.counts)
        facts.extend(f"name:{value}" for value in self.names)
        facts.extend(f"id:{value}" for value in self.ids)
        facts.extend(f"status:{value}" for value in self.statuses)
        facts.extend(f"date:{value}" for value in self.dates)
        facts.extend(f"relationship:{value}" for value in self.relationships)
        return facts[:limit]


def build_allowed_fact_index(
    *,
    answer_card: Any | None = None,
    slots: AnswerSlots | None = None,
    evidence_bus: EvidenceBus | dict[str, Any] | None = None,
    caveats: list[str] | None = None,
    missing_roles: list[str] | None = None,
) -> AllowedFactIndex:
    counts: list[str] = []
    names: list[str] = []
    ids: list[str] = []
    statuses: list[str] = []
    dates: list[str] = []
    relationships: list[str] = []
    allowed_caveats: list[str] = []
    live_empty_scopes: list[str] = []
    api_error_scopes: list[str] = []
    missing: list[str] = []
    evidence_strings: list[str] = []

    if slots is not None:
        counts.extend(_number_variants(value) for value in slots.counts)
        if slots.sql_row_count is not None:
            counts.append(_norm_number(slots.sql_row_count))
        if slots.api_item_count is not None:
            counts.append(_norm_number(slots.api_item_count))
        names.extend(slots.entity_names)
        ids.extend(slots.entity_ids)
        ids.extend(str(value) for value in getattr(slots, "api_ids", []) if value)
        statuses.extend(slots.statuses)
        dates.extend(slots.timestamps)
        evidence_strings.extend(str(value) for value in slots.evidence_strings)
        for row in [*slots.first_rows, *slots.api_items, *slots.important_rows, *slots.important_items]:
            if isinstance(row, dict):
                _collect_mapping_facts(row, names, ids, statuses, dates, counts, evidence_strings)
        if slots.api_evidence_state and "empty" in str(slots.api_evidence_state).lower():
            allowed_caveats.append("API_LIVE_EMPTY")
            live_empty_scopes.append("query/scope")
        if slots.api_error or slots.api_errors or str(slots.answer_slot_source or "").lower() == "api_error":
            allowed_caveats.append("API_ERROR")
            api_error_scopes.append("live api verification")
        if slots.dry_run:
            allowed_caveats.append("DRY_RUN_UNAVAILABLE")
            api_error_scopes.append("live api verification")

    bus_payload = _bus_payload(evidence_bus)
    if bus_payload:
        names.extend(_list(bus_payload.get("names")))
        names.extend(_list(bus_payload.get("api_names")))
        ids.extend(str(value) for value in _list(bus_payload.get("api_ids")))
        ids.extend(str(value) for value in (bus_payload.get("ids") or {}).values() if value) if isinstance(bus_payload.get("ids"), dict) else []
        statuses.extend(_list(bus_payload.get("statuses")))
        statuses.extend(_list(bus_payload.get("api_statuses")))
        dates.extend(_list(bus_payload.get("timestamps")))
        dates.extend(_list(bus_payload.get("api_timestamps")))
        counts.extend(_norm_number(value) for value in _list(bus_payload.get("counts")))
        counts.extend(_norm_number(value) for value in _list(bus_payload.get("api_counts")))
        if any("empty" in _normalize_text(value) for value in _list(bus_payload.get("api_evidence_states"))):
            allowed_caveats.append("API_LIVE_EMPTY")
            live_empty_scopes.append("query/scope")
        if _list(bus_payload.get("api_errors")):
            allowed_caveats.append("API_ERROR")
            api_error_scopes.append("live api verification")

    card_payload = _safe_card_payload(answer_card)
    renderer = card_payload.get("renderer") if isinstance(card_payload.get("renderer"), dict) else {}
    quality = card_payload.get("evidence_quality") if isinstance(card_payload.get("evidence_quality"), dict) else {}
    if isinstance(renderer, dict):
        allowed_caveats.extend(str(value) for value in renderer.get("caveats", []) if value)
        missing.extend(str(value).upper() for value in renderer.get("missing_fields", []) if value)
    if isinstance(quality, dict):
        if "API_LIVE_EMPTY" in set(quality.get("api") or []):
            allowed_caveats.append("API_LIVE_EMPTY")
            live_empty_scopes.append("query/scope")
        if "API_ERROR" in set(quality.get("api") or []):
            allowed_caveats.append("API_ERROR")
            api_error_scopes.append("live api verification")
        if "SQL_ZERO_ROWS" in set(quality.get("sql") or []):
            allowed_caveats.append("SQL_EMPTY")
            live_empty_scopes.append("local snapshot")

    for caveat in caveats or []:
        normalized = str(caveat).upper()
        allowed_caveats.append(normalized)
        if "LIVE_EMPTY" in normalized or "SQL_EMPTY" in normalized:
            live_empty_scopes.append("query/scope")
        if "API_ERROR" in normalized or "UNAVAILABLE" in normalized:
            api_error_scopes.append("live api verification")
    missing.extend(str(role).upper() for role in missing_roles or [])

    return AllowedFactIndex(
        counts=_dedupe([value for value in _flatten(counts) if value]),
        names=_dedupe([_normalize_text(value) for value in names if value]),
        ids=_dedupe([str(value).strip().lower() for value in ids if value]),
        statuses=_dedupe([_normalize_status(value) for value in statuses if value]),
        dates=_dedupe(_date_variants(value) for value in dates if value),
        relationships=_dedupe([_normalize_text(value) for value in relationships if value]),
        allowed_caveats=_dedupe([_normalize_caveat(value) for value in allowed_caveats if value]),
        live_empty_scopes=_dedupe([_normalize_text(value) for value in live_empty_scopes if value]),
        api_error_scopes=_dedupe([_normalize_text(value) for value in api_error_scopes if value]),
        missing_roles=_dedupe([str(value).upper() for value in missing if value]),
        evidence_strings=_dedupe([_normalize_text(value) for value in evidence_strings if value]),
    )


def _safe_card_payload(answer_card: Any | None) -> dict[str, Any]:
    if answer_card is None:
        return {}
    if hasattr(answer_card, "to_dict"):
        payload = answer_card.to_dict()
    elif isinstance(answer_card, dict):
        payload = dict(answer_card)
    else:
        payload = {}
    return {key: value for key, value in payload.items() if str(key) not in SENSITIVE_CARD_KEYS}


def _collect_mapping_facts(
    mapping: dict[str, Any],
    names: list[str],
    ids: list[str],
    statuses: list[str],
    dates: list[str],
    counts: list[str],
    evidence_strings: list[str],
) -> None:
    for key, value in mapping.items():
        if value in (None, "", [], {}):
            continue
        key_norm = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if isinstance(value, dict):
            _collect_mapping_facts(value, names, ids, statuses, dates, counts, evidence_strings)
            continue
        if isinstance(value, list):
            for item in value[:5]:
                if isinstance(item, dict):
                    _collect_mapping_facts(item, names, ids, statuses, dates, counts, evidence_strings)
            continue
        text = str(value)
        evidence_strings.append(text)
        if key_norm in {"id", "_id", "campaignid", "campaign_id", "schemaid", "schema_id", "audienceid", "segmentid"} or _looks_like_id(text):
            ids.append(text)
        if key_norm in {"name", "title", "campaignname", "campaign_name", "displayname", "collectionname", "collection_name", "datasetname"}:
            names.append(text)
        if key_norm in {"status", "state", "lifecyclestatus", "campaignstate", "processingstatus"}:
            statuses.append(text)
        if "time" in key_norm or "date" in key_norm or key_norm in {"created", "updated", "modified"}:
            dates.append(text)
        if "count" in key_norm or key_norm in {"total", "totalprofiles", "totalmembers"}:
            counts.append(_norm_number(text))


def _bus_payload(evidence_bus: EvidenceBus | dict[str, Any] | None) -> dict[str, Any]:
    if evidence_bus is None:
        return {}
    if isinstance(evidence_bus, EvidenceBus):
        return evidence_bus.compact()
    if isinstance(evidence_bus, dict):
        return dict(evidence_bus)
    return {}


def _number_variants(value: Any) -> list[str]:
    normalized = _norm_number(value)
    return [normalized] if normalized else []


def _norm_number(value: Any) -> str:
    return re.sub(r"[^\d.]", "", str(value))


def _date_variants(value: Any) -> list[str]:
    text = str(value)
    normalized = _normalize_text(text)
    variants = [normalized]
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    if match:
        variants.append(match.group(0).lower())
    return variants


def _normalize_status(value: Any) -> str:
    text = _normalize_text(value)
    aliases = {
        "success": "succeeded",
        "successful": "succeeded",
        "failure": "failed",
        "running": "active",
    }
    return aliases.get(text, text)


def _normalize_caveat(value: Any) -> str:
    text = str(value).upper()
    if "LIVE_EMPTY" in text or "NO MATCHING" in text:
        return "API_LIVE_EMPTY"
    if "SQL_EMPTY" in text or "ZERO_ROWS" in text:
        return "SQL_EMPTY"
    if "API_ERROR" in text or "UNAVAILABLE" in text or "ERROR" in text:
        return "API_ERROR"
    if "DRY_RUN" in text:
        return "DRY_RUN_UNAVAILABLE"
    return text


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _looks_like_id(text: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+-\d+", text, flags=re.I) or re.fullmatch(r"01[A-Z0-9]{20,}", text) or re.fullmatch(r"[0-9a-f-]{32,36}", text, flags=re.I))


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _flatten(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, list):
            out.extend(str(item) for item in value if item)
        elif value:
            out.append(str(value))
    return out


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in _flatten(values):
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
