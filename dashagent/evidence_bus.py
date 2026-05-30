from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from .live_response_parsers import normalize_api_evidence


ID_KEYS = {
    "targetid": "target_id",
    "target_id": "target_id",
    "destinationid": "destination_id",
    "destination_id": "destination_id",
    "segmentid": "segment_id",
    "segment_id": "segment_id",
    "campaignid": "campaign_id",
    "campaign_id": "campaign_id",
    "blueprintid": "schema_id",
    "blueprint_id": "schema_id",
    "schemaid": "schema_id",
    "schema_id": "schema_id",
    "collectionid": "collection_id",
    "collection_id": "collection_id",
    "batchid": "batch_id",
    "batch_id": "batch_id",
    "tagid": "tag_id",
    "tag_id": "tag_id",
    "id": "id",
}


@dataclass
class EvidenceBus:
    names: list[str] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)
    timestamps: list[str] = field(default_factory=list)
    counts: list[Any] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    first_rows: list[dict[str, Any]] = field(default_factory=list)
    api_items: list[dict[str, Any]] = field(default_factory=list)
    api_ids: list[str] = field(default_factory=list)
    api_names: list[str] = field(default_factory=list)
    api_statuses: list[str] = field(default_factory=list)
    api_counts: list[Any] = field(default_factory=list)
    api_timestamps: list[str] = field(default_factory=list)
    api_errors: list[str] = field(default_factory=list)
    api_pagination: list[dict[str, Any]] = field(default_factory=list)
    api_evidence_states: list[str] = field(default_factory=list)
    api_parser_modes: list[str] = field(default_factory=list)
    pass_results: list[dict[str, Any]] = field(default_factory=list)

    def observe_sql(self, step: Any, payload: dict[str, Any]) -> None:
        if not payload.get("ok"):
            return
        rows = payload.get("rows") or []
        if rows:
            self.first_rows.extend(copy.deepcopy(rows[:3]))
        for row in rows[:10]:
            self._observe_mapping(row)

    def observe_api(self, step: Any, payload: dict[str, Any]) -> None:
        family = getattr(step, "family", None) or ""
        parsed = payload.get("parsed_evidence") if isinstance(payload, dict) else None
        if isinstance(parsed, dict):
            state = parsed.get("evidence_state")
            if state:
                append_unique(self.api_evidence_states, str(state))
            mode = parsed.get("parser_mode")
            if mode:
                append_unique(self.api_parser_modes, str(mode))
            for value in parsed.get("ids", []) if isinstance(parsed.get("ids"), list) else []:
                append_unique(self.api_ids, str(value))
            for value in parsed.get("names", []) if isinstance(parsed.get("names"), list) else []:
                append_unique(self.api_names, str(value))
            for value in parsed.get("statuses", []) if isinstance(parsed.get("statuses"), list) else []:
                append_unique(self.api_statuses, str(value))
            counts = parsed.get("counts")
            if isinstance(counts, dict):
                self.api_counts.extend(value for value in counts.values() if value not in (None, "", [], {}))
            timestamps = parsed.get("timestamps")
            if isinstance(timestamps, dict):
                for value in timestamps.values():
                    append_unique(self.api_timestamps, str(value))
            pagination = parsed.get("pagination")
            if isinstance(pagination, dict) and pagination:
                self.api_pagination.append(copy.deepcopy(pagination))
            for error in parsed.get("errors", []) if isinstance(parsed.get("errors"), list) else []:
                append_unique(self.api_errors, str(error))

        evidence = normalize_api_evidence(str(family), payload)
        if evidence.get("errors") and not evidence.get("items"):
            return
        for item in evidence.get("items", [])[:10]:
            if isinstance(item, dict):
                self.api_items.append(copy.deepcopy(item))
                self._observe_mapping(item)
        fields = evidence.get("important_fields", {})
        if isinstance(fields, dict):
            self._observe_mapping(fields)

    def observe_pass_result(self, pass_result: dict[str, Any]) -> None:
        if not isinstance(pass_result, dict):
            return
        self.pass_results.append(
            {
                "pass_id": pass_result.get("pass_id"),
                "path": pass_result.get("path"),
                "status": pass_result.get("status"),
                "depends_on": list(pass_result.get("depends_on") or []),
                "facts": list(pass_result.get("facts") or [])[:10],
                "source_result_count": len(pass_result.get("source_results") or []),
            }
        )

    def forward_to_step(self, step: Any) -> list[str]:
        actions: list[str] = []
        if getattr(step, "action", None) != "api":
            return actions
        params = dict(getattr(step, "params", {}) or {})
        url = getattr(step, "url", None) or ""

        property_value = params.get("property")
        destination_id = self.ids.get("destination_id") or self.ids.get("target_id")
        if isinstance(property_value, str) and "<destination_id>" in property_value and destination_id:
            params["property"] = property_value.replace("<destination_id>", destination_id)
            actions.append("forwarded target_id to destinationId API param")

        schema_id = self.ids.get("schema_id")
        if "{schema_id}" in url and schema_id:
            step.url = url.replace("{schema_id}", schema_id)
            actions.append("forwarded schema_id to schema registry path")

        if getattr(step, "family", "") == "journey_by_name" and "filter" not in params and self.names:
            params["filter"] = f"name=={self.names[0]}"
            actions.append("forwarded campaign name to journey API filter")

        if params != getattr(step, "params", {}):
            step.params = params
        return actions

    def _observe_mapping(self, mapping: dict[str, Any]) -> None:
        for key, value in mapping.items():
            if value in (None, ""):
                continue
            normalized = normalize_key(key)
            if normalized in ID_KEYS:
                self.ids.setdefault(ID_KEYS[normalized], str(value))
            if normalized in {"name", "campaignname", "campaign_name", "segmentname", "segment_name", "title"}:
                append_unique(self.names, str(value))
            if "time" in normalized or "date" in normalized or normalized in {"modified", "updated", "created"}:
                append_unique(self.timestamps, str(value))
            if "count" in normalized or normalized in {"total", "totalmembers", "totalprofiles"}:
                self.counts.append(value)
            if normalized in {"status", "state", "lifecyclestatus"}:
                append_unique(self.statuses, str(value))

    def compact(self) -> dict[str, Any]:
        return {
            "names": self.names[:3],
            "ids": self.ids,
            "timestamps": self.timestamps[:3],
            "counts": self.counts[:3],
            "statuses": self.statuses[:3],
            "api_ids": self.api_ids[:5],
            "api_names": self.api_names[:5],
            "api_statuses": self.api_statuses[:5],
            "api_counts": self.api_counts[:5],
            "api_timestamps": self.api_timestamps[:5],
            "api_errors": self.api_errors[:3],
            "api_pagination": self.api_pagination[:2],
            "api_evidence_states": self.api_evidence_states[:5],
            "api_parser_modes": self.api_parser_modes[:5],
            "pass_result_count": len(self.pass_results),
            "pass_ids": [str(item.get("pass_id")) for item in self.pass_results[:6] if item.get("pass_id")],
        }


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", key.lower())


def append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
