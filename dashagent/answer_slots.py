from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_templates import classify_answer_family, extract_dates, extract_metric_names
from .live_response_parsers import normalize_api_evidence


ID_KEYS = {
    "id",
    "_id",
    "@id",
    "campaignid",
    "campaign_id",
    "journeyid",
    "journey_id",
    "segmentid",
    "segment_id",
    "audienceid",
    "audience_id",
    "targetid",
    "target_id",
    "destinationid",
    "destination_id",
    "schemaid",
    "schema_id",
    "batchid",
    "batch_id",
    "tagid",
    "tag_id",
    "flowid",
    "flow_id",
    "runid",
    "run_id",
}

NAME_KEYS = {"name", "title", "campaign_name", "segment_name", "audience_name", "target_name", "collection_name", "dataset_name", "blueprint_name", "property_name", "filename", "file_name"}
STATUS_KEYS = {"status", "state", "lifecycle_status", "lifecyclestatus", "campaign_state", "processing_status", "processingstatus"}
TIME_KEYS = {"timestamp", "date", "time", "created", "createdtime", "created_time", "updated", "updatedtime", "updated_time", "published_time", "lastdeployedtime", "modified"}
COUNT_KEYS = {"count", "total", "total_count", "totalcount", "row_count", "collection_count", "property_count", "total_profiles", "totalprofiles", "totalmembers"}


@dataclass
class AnswerSlots:
    query: str
    answer_family: str
    entity_names: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    counts: list[Any] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    date_ranges: list[str] = field(default_factory=list)
    sql_row_count: int | None = None
    api_item_count: int | None = None
    dry_run: bool = False
    api_error: bool = False
    live_api_evidence_available: bool = False
    api_evidence_state: str | None = None
    answer_slot_source: str | None = None
    api_errors: list[str] = field(default_factory=list)
    api_pagination: list[dict[str, Any]] = field(default_factory=list)
    api_parser_modes: list[str] = field(default_factory=list)
    discrepancy: bool = False
    first_rows: list[dict[str, Any]] = field(default_factory=list)
    api_items: list[dict[str, Any]] = field(default_factory=list)
    important_rows: list[dict[str, Any]] = field(default_factory=list)
    important_items: list[dict[str, Any]] = field(default_factory=list)
    evidence_strings: set[str] = field(default_factory=set)
    evidence_numbers: set[str] = field(default_factory=set)

    def slots_present(self) -> list[str]:
        present = []
        for name in [
            "entity_names",
            "entity_ids",
            "counts",
            "statuses",
            "timestamps",
            "metrics",
            "date_ranges",
            "sql_row_count",
            "api_item_count",
            "dry_run",
            "api_error",
            "live_api_evidence_available",
            "api_evidence_state",
            "answer_slot_source",
            "api_errors",
            "api_pagination",
            "api_parser_modes",
            "discrepancy",
            "first_rows",
            "api_items",
        ]:
            value = getattr(self, name)
            if name == "api_errors" and _only_synthetic_dry_run_errors(value):
                continue
            if value not in (None, False, [], {}, set(), ""):
                present.append(name)
        return present

    def compact(self) -> dict[str, Any]:
        payload = {
            "answer_family": self.answer_family,
            "slots_present": self.slots_present(),
            "sql_row_count": self.sql_row_count,
            "api_item_count": self.api_item_count,
            "dry_run": self.dry_run,
            "api_error": self.api_error,
            "discrepancy": self.discrepancy,
            "entity_names": self.entity_names[:3],
            "entity_ids": self.entity_ids[:3],
            "counts": [str(value) for value in self.counts[:3]],
            "statuses": self.statuses[:3],
            "timestamps": self.timestamps[:3],
            "metrics": self.metrics[:2],
        }
        live_fields = {
            "live_api_evidence_available": self.live_api_evidence_available,
            "api_evidence_state": self.api_evidence_state,
            "answer_slot_source": self.answer_slot_source,
            "api_errors": [] if _only_synthetic_dry_run_errors(self.api_errors) else self.api_errors[:3],
            "api_pagination": self.api_pagination[:2],
            "api_parser_modes": self.api_parser_modes[:3],
        }
        for key, value in live_fields.items():
            if value not in (None, False, [], {}, set(), ""):
                payload[key] = value
        return payload


def extract_answer_slots(query: str, tool_results: list[dict[str, Any]]) -> AnswerSlots:
    slots = AnswerSlots(
        query=query,
        answer_family=classify_answer_family(query),
        metrics=dedupe(extract_metric_names(query)),
        date_ranges=extract_dates(query),
    )
    add_query_evidence(slots, query)

    sql_counts: list[int] = []
    live_api_counts: list[int] = []
    saw_live_api = False
    for result in tool_results:
        kind = result.get("type")
        payload = result.get("payload", {})
        if kind == "sql":
            rows = coerce_rows(payload.get("rows"))
            if payload.get("ok"):
                row_count = int(payload.get("row_count", len(rows)) or 0)
                slots.sql_row_count = row_count
                slots.counts.append(row_count)
                slots.evidence_numbers.add(str(row_count))
                sql_counts.append(row_count)
                slots.first_rows = rows[:3]
                slots.important_rows = rows[:3]
                for row in rows[:10]:
                    collect_mapping(slots, row)
        elif kind == "api":
            parsed = payload.get("parsed_evidence") if isinstance(payload, dict) else None
            if isinstance(parsed, dict):
                state = parsed.get("evidence_state")
                if state:
                    slots.api_evidence_state = str(state)
                mode = parsed.get("parser_mode")
                if mode:
                    slots.api_parser_modes.append(str(mode))
                pagination = parsed.get("pagination")
                if isinstance(pagination, dict) and pagination:
                    slots.api_pagination.append(pagination)
                for error in parsed.get("errors", []) if isinstance(parsed.get("errors"), list) else []:
                    slots.api_errors.append(str(error))
                if parsed.get("live_evidence_available"):
                    slots.live_api_evidence_available = True
                    slots.answer_slot_source = "live_api"
                elif parsed.get("dry_run"):
                    slots.answer_slot_source = slots.answer_slot_source or "dry_run_unavailable"
                elif parsed.get("evidence_state") in {"api_error", "malformed_response"}:
                    slots.answer_slot_source = slots.answer_slot_source or str(parsed.get("evidence_state"))
            if payload.get("dry_run"):
                slots.dry_run = True
            if not payload.get("ok") and not payload.get("dry_run"):
                slots.api_error = True
                slots.answer_slot_source = slots.answer_slot_source or "api_error"
            step = result.get("step", {})
            collect_api_request_evidence(slots, step, payload)
            family = str(step.get("family") or slots.answer_family)
            evidence = normalize_api_evidence(family, payload)
            if not payload.get("dry_run") and payload.get("ok"):
                saw_live_api = True
                count = int(evidence.get("count", 0) or 0)
                slots.api_item_count = count
                slots.counts.append(count)
                slots.evidence_numbers.add(str(count))
                live_api_counts.append(count)
                slots.answer_slot_source = "live_api"
                if count or evidence.get("items") or not evidence.get("empty"):
                    slots.live_api_evidence_available = True
            items = [item for item in evidence.get("items", []) if isinstance(item, dict)]
            slots.api_items.extend(items[:3])
            slots.important_items.extend(items[:3])
            important = evidence.get("important_fields") or {}
            if isinstance(important, dict):
                collect_mapping(slots, important)
            for item in items[:10]:
                collect_mapping(slots, item)
            if evidence.get("errors"):
                slots.api_errors.extend(str(error) for error in evidence.get("errors", [])[:5])
                if any(error != "dry_run" for error in evidence.get("errors", [])):
                    slots.api_error = True

    if saw_live_api and slots.sql_row_count is not None and slots.api_item_count is not None:
        slots.discrepancy = slots.sql_row_count == 0 and slots.api_item_count > 0
    if sql_counts and live_api_counts and sql_counts[0] > 0 and live_api_counts[0] > 0 and sql_counts[0] != live_api_counts[0]:
        slots.discrepancy = True

    slots.entity_names = dedupe(slots.entity_names)
    slots.entity_ids = dedupe(slots.entity_ids)
    slots.statuses = dedupe(slots.statuses)
    slots.timestamps = dedupe(slots.timestamps)
    slots.counts = dedupe_values(slots.counts)
    slots.api_errors = dedupe(slots.api_errors)
    slots.api_parser_modes = dedupe(slots.api_parser_modes)
    return slots


def _only_synthetic_dry_run_errors(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(str(item) == "dry_run" for item in value)


def add_query_evidence(slots: AnswerSlots, query: str) -> None:
    for quoted in re.findall(r"'([^']+)'|\"([^\"]+)\"", query):
        value = (quoted[0] or quoted[1]).strip()
        if value:
            slots.entity_names.append(value)
            slots.evidence_strings.add(normalize_text(value))
    for value in re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", query, flags=re.I):
        slots.entity_ids.append(value)
        slots.evidence_strings.add(normalize_text(value))
    for value in re.findall(r"\b01[A-Z0-9]{20,}\b", query):
        slots.entity_ids.append(value)
        slots.evidence_strings.add(normalize_text(value))
    for value in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query):
        slots.timestamps.append(value)
        slots.evidence_strings.add(normalize_text(value))
    for value in re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w.-])", query):
        slots.evidence_numbers.add(value)


def collect_mapping(slots: AnswerSlots, mapping: dict[str, Any]) -> None:
    for key, value in mapping.items():
        if value in (None, "", [], {}):
            continue
        key_norm = normalize_key(str(key))
        if isinstance(value, (dict, list)):
            slots.evidence_strings.add(normalize_text(value))
            if isinstance(value, dict):
                collect_mapping(slots, value)
            elif isinstance(value, list):
                for item in value[:5]:
                    if isinstance(item, dict):
                        collect_mapping(slots, item)
            continue
        text = str(value)
        slots.evidence_strings.add(normalize_text(text))
        for number in re.findall(r"\b\d+(?:\.\d+)?\b", text):
            slots.evidence_numbers.add(number)
        if key_norm in {normalize_key(key) for key in NAME_KEYS}:
            slots.entity_names.append(text)
        if key_norm in {normalize_key(key) for key in ID_KEYS} or looks_like_id(text):
            slots.entity_ids.append(text)
        if key_norm in {normalize_key(key) for key in STATUS_KEYS}:
            slots.statuses.append(text)
        if key_norm in {normalize_key(key) for key in TIME_KEYS} or re.match(r"20\d{2}-\d{2}-\d{2}", text):
            slots.timestamps.append(text)
        if looks_like_count_key(key_norm) and re.search(r"\d", text):
            slots.counts.append(value)
            slots.evidence_numbers.add(re.sub(r"[^\d.]", "", text) or text)


def collect_api_request_evidence(slots: AnswerSlots, step: dict[str, Any], payload: dict[str, Any]) -> None:
    path = str(step.get("url") or payload.get("endpoint") or "")
    if path:
        slots.evidence_strings.add(normalize_text(path))
        collect_mapping(slots, {"endpoint": path})
    params = step.get("params") or payload.get("params") or {}
    if isinstance(params, dict):
        safe_params = {}
        for key, value in params.items():
            key_norm = normalize_key(str(key))
            if any(part in key_norm for part in ["token", "secret", "password", "authorization", "clientid", "clientsecret", "apikey", "key"]):
                continue
            if isinstance(value, (dict, list)) or value in (None, ""):
                continue
            safe_params[str(key)] = value
        collect_mapping(slots, safe_params)


def coerce_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return [row for row in value["items"] if isinstance(row, dict)]
    return []


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def looks_like_id(text: str) -> bool:
    return bool(
        re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, flags=re.I)
        or re.fullmatch(r"01[A-Z0-9]{20,}", text)
    )


def looks_like_count_key(key_norm: str) -> bool:
    count_keys = {normalize_key(key) for key in COUNT_KEYS}
    return (
        key_norm in count_keys
        or key_norm.endswith("count")
        or key_norm.endswith("counts")
        or key_norm.startswith("num")
        or key_norm.startswith("numberof")
    )


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output = []
    for item in items:
        key = normalize_text(item)
        if key and key not in seen:
            seen.add(key)
            output.append(item)
    return output


def dedupe_values(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output = []
    for item in items:
        key = str(item)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output
