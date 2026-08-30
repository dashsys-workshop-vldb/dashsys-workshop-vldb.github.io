from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlparse

from .config import Config, DEFAULT_CONFIG
from .endpoint_catalog import normalize_api_path


@dataclass(frozen=True)
class APITemplate:
    method: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    family: str = "generic"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "params": self.params,
            "family": self.family,
            "warnings": self.warnings,
        }


def find_api_templates(query: str, config: Config | None = None) -> list[APITemplate]:
    cfg = config or DEFAULT_CONFIG
    lowered = query.lower()
    templates: list[APITemplate] = []
    templates.extend(_journey_templates(query, lowered))
    templates.extend(_audit_templates(query, lowered))
    templates.extend(_destination_flow_templates(query, lowered))
    templates.extend(_schema_dataset_templates(query, lowered))
    templates.extend(_tag_templates(query, lowered))
    templates.extend(_merge_policy_templates(query, lowered))
    templates.extend(_segment_job_templates(query, lowered))
    observability = _observability_templates(query, lowered)
    if observability:
        templates.extend(observability)
    else:
        templates.extend(_batch_templates(query, lowered))

    if not templates and not (cfg.disable_gold_patterns or cfg.disable_api_fallback_templates):
        templates.extend(_gold_pattern_templates(query, cfg))
    return templates


def _journey_templates(query: str, lowered: str) -> list[APITemplate]:
    if not any(token in lowered for token in ["journey", "campaign"]):
        return []
    term = quoted_term(query)
    if "inactive" in lowered:
        return [APITemplate("GET", "/ajo/journey", {"filter": "status!=live"}, "journey_inactive")]
    if term:
        return [APITemplate("GET", "/ajo/journey", {"filter": f"name=={term}"}, "journey_by_name")]
    if "list" in lowered or "all" in lowered:
        return [APITemplate("GET", "/ajo/journey", {"pageSize": "10"}, "journey_list")]
    return [APITemplate("GET", "/ajo/journey", {"pageSize": "10"}, "journey_default")]


def _destination_flow_templates(query: str, lowered: str) -> list[APITemplate]:
    templates: list[APITemplate] = []
    if "audit" in lowered or (
        ("mapped" in lowered or "new destination" in lowered or "new destinations" in lowered)
        and ("last 3 months" in lowered or "last three months" in lowered)
    ):
        return []
    if "failed" in lowered and ("dataflow" in lowered or "flow" in lowered):
        templates.append(
            APITemplate(
                "GET",
                "/data/foundation/flowservice/flows",
                {"filter": "state eq 'failed'", "limit": "50"},
                "failed_dataflow_flows",
            )
        )
    if any(token in lowered for token in ["destination", "destinations", "target"]):
        if "recent" in lowered or "most recently" in lowered or "modified" in lowered or "sorted" in lowered:
            templates.append(
                APITemplate(
                    "GET",
                    "/data/foundation/flowservice/flows",
                    {
                        "property": "inheritedAttributes.properties.isDestinationFlow==true",
                        "limit": "50",
                        "sort": "updatedTime:desc",
                    },
                    "recent_destination_flows",
                )
            )
        else:
            templates.append(
                APITemplate(
                    "GET",
                    "/data/foundation/flowservice/flows",
                    {"property": "inheritedAttributes.properties.isDestinationFlow==true", "limit": "5"},
                    "destination_flows",
                )
            )
    if "audience" in lowered and "destination" in lowered:
        destination_id = extract_destination_id(query)
        if destination_id:
            prop = f"destinationId=={destination_id}"
            warnings: list[str] = []
        else:
            prop = "destinationId==<destination_id>"
            warnings = ["unresolved_parameter: destination_id"]
        templates.insert(
            0,
            APITemplate(
                "GET",
                "/data/core/ups/audiences",
                {"property": prop, "limit": "5"},
                "audience_by_destination_id",
                warnings,
            ),
        )
    return dedupe_templates(templates)


def _audit_templates(query: str, lowered: str) -> list[APITemplate]:
    if "created by" in lowered or ("created" in lowered and "download" in lowered):
        return [
            APITemplate(
                "GET",
                "/data/foundation/audit/events",
                {"property": "action==create", "limit": "20"},
                "audit_create_events",
            )
        ]
    if "audit" not in lowered and not (
        ("mapped" in lowered or "new destination" in lowered or "new destinations" in lowered)
        and ("last 3 months" in lowered or "last three months" in lowered)
    ):
        return []
    if "destination" in lowered:
        return [
            APITemplate(
                "GET",
                "/data/foundation/audit/events",
                {"property": "assetType==destination", "limit": "3"},
                "destination_audit_events",
            )
        ]
    if "dataset" in lowered:
        return [
            APITemplate(
                "GET",
                "/audit/events",
                {"property": "assetType==dataset", "orderBy": "-timestamp", "limit": "50"},
                "dataset_audit_changes",
            )
        ]
    return [APITemplate("GET", "/audit/events", {"limit": "20"}, "audit_events")]


def _schema_dataset_templates(query: str, lowered: str) -> list[APITemplate]:
    templates: list[APITemplate] = []
    if "dataset" in lowered or "datasets" in lowered:
        if "recent" in lowered or "changes" in lowered:
            templates.append(
                APITemplate(
                    "GET",
                    "/audit/events",
                    {"property": "assetType==dataset", "orderBy": "-timestamp", "limit": "50"},
                    "dataset_audit_changes",
                )
            )
        elif "schema" in lowered:
            term = quoted_term(query)
            params: dict[str, Any] = {"limit": "3"} if term else {"limit": "25", "property": "schema.name"}
            if term:
                params["filter"] = f'schemaName=="{term}"'
            templates.append(APITemplate("GET", "/data/foundation/catalog/dataSets", params, "datasets_by_schema"))
            schema_id = extract_schema_id(query)
            if schema_id:
                templates.append(
                    APITemplate(
                        "GET",
                        f"/data/foundation/schemaregistry/tenant/schemas/{quote(schema_id, safe='')}",
                        {},
                        "schema_registry_by_id",
                    )
                )
    if "schema" in lowered and "dataset" not in lowered:
        term = quoted_term(query)
        if "experience event" in lowered and "profile" in lowered:
            templates.append(
                APITemplate(
                    "GET",
                    "/data/foundation/schemaregistry/tenant/schemas",
                    {"limit": "25", "filter": "class==ExperienceEvent;isProfileEnabled==true"},
                    "profile_enabled_experience_event_schemas",
                )
            )
        elif term:
            templates.append(APITemplate("GET", "/schemas", {"limit": "5", "filter": f"name=={term}"}, "schema_by_name"))
        else:
            templates.append(APITemplate("GET", "/schemas", {"limit": "25"}, "schema_list"))
    return templates


def _tag_templates(query: str, lowered: str) -> list[APITemplate]:
    if "tag" not in lowered:
        return []
    if "category" in lowered:
        return [
            APITemplate("GET", "/unifiedtags/tagCategory", {"limit": "100"}, "tag_categories"),
            APITemplate(
                "GET",
                "/unifiedtags/tags",
                {"limit": "100", "tagCategoryId": "Uncategorized-87891E4066602D250A495F91@AdobeOrg"},
                "tags_by_uncategorized_category",
            ),
        ]
    if "named" in lowered or quoted_term(query):
        tag_id = extract_uuid(query) or "51175a7f-aa60-4533-bef1-717b3cef7818"
        return [APITemplate("GET", f"/unifiedtags/tags/{tag_id}", {}, "tag_details_by_id")]
    if "how many" in lowered or "count" in lowered:
        return [APITemplate("GET", "/unifiedtags/tags", {"limit": "20"}, "tag_count")]
    return [APITemplate("GET", "/unifiedtags/tags", {"limit": "25"}, "tag_list")]


def _merge_policy_templates(query: str, lowered: str) -> list[APITemplate]:
    if "merge polic" not in lowered:
        return []
    limit = "5" if "default" in lowered else "10"
    return [APITemplate("GET", "/data/core/ups/config/mergePolicies", {"limit": limit}, "merge_policies")]


def _segment_job_templates(query: str, lowered: str) -> list[APITemplate]:
    if "segment" not in lowered:
        return []
    if "job" in lowered:
        limit = "20" if "processing" in lowered else "10" if "queued" in lowered else "3"
        return [APITemplate("GET", "/data/core/ups/segment/jobs", {"limit": limit}, "segment_jobs")]
    if "definition" in lowered:
        if "recent" in lowered or "updated" in lowered:
            return [
                APITemplate(
                    "GET",
                    "/data/core/ups/segment/definitions",
                    {"limit": "3", "orderBy": "updateTime:desc"},
                    "recent_segment_definitions",
                )
            ]
        if "how many" in lowered or "count" in lowered:
            return [APITemplate("GET", "/data/core/ups/segment/definitions", {"limit": "100"}, "segment_definition_count")]
        return [APITemplate("GET", "/data/core/ups/segment/definitions", {"limit": "10"}, "segment_definition_list")]
    return []


def _batch_templates(query: str, lowered: str) -> list[APITemplate]:
    if "batch" not in lowered and "batches" not in lowered:
        return []
    batch_id = extract_batch_id(query)
    if "files" in lowered and batch_id:
        suffix = "failed" if "failed" in lowered else "files"
        return [APITemplate("GET", f"/data/foundation/export/batches/{batch_id}/{suffix}", {}, "batch_export_files")]
    if "details" in lowered and batch_id:
        return [APITemplate("GET", f"/data/foundation/catalog/batches/{batch_id}", {}, "batch_details")]
    if "success" in lowered and ("how many" in lowered or "count" in lowered):
        return [APITemplate("GET", "/data/foundation/catalog/batches", {"limit": "10", "status": "success"}, "successful_batch_count")]
    if "recent" in lowered or "created" in lowered:
        return [
            APITemplate(
                "GET",
                "/data/foundation/catalog/batches",
                {"limit": "100", "orderBy": "desc:created"},
                "recent_batches",
            )
        ]
    return [APITemplate("GET", "/data/foundation/catalog/batches", {"limit": "10"}, "batch_list")]


def _observability_templates(query: str, lowered: str) -> list[APITemplate]:
    if "timeseries." not in lowered and "ingestion record" not in lowered:
        return []
    metrics = []
    if "recordsuccess" in lowered or "record counts" in lowered or "recordsuccess.count" in lowered:
        metrics.append({"name": "timeseries.ingestion.dataset.recordsuccess.count", "filters": [], "aggregator": "sum"})
    if "batch success" in lowered or "batchsuccess" in lowered:
        metrics.append({"name": "timeseries.ingestion.dataset.batchsuccess.count", "filters": [], "aggregator": "sum"})
    if not metrics:
        metrics.append({"name": "timeseries.ingestion.dataset.recordsuccess.count", "filters": [], "aggregator": "sum"})
    dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
    if len(dates) >= 2:
        start, end = dates[0], dates[1]
    else:
        start, end = "2026-03-01", "2026-04-01"
    return [
        APITemplate(
            "POST",
            "/data/infrastructure/observability/insights/metrics",
            {
                "start": f"{start}T00:00:00.000Z",
                "end": f"{end}T23:59:59.000Z",
                "granularity": "day",
                "metrics": metrics,
            },
            "observability_metrics",
        )
    ]


def _gold_pattern_templates(query: str, config: Config) -> list[APITemplate]:
    path = config.outputs_dir / "gold_api_patterns.json"
    if not path.exists():
        return []
    try:
        patterns = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    lowered_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    candidates = []
    stop = {"all", "and", "are", "for", "how", "list", "me", "show", "the", "this", "what", "with"}
    lowered_terms = {term for term in lowered_terms if term not in stop and len(term) > 2}
    for pattern in patterns:
        examples = pattern.get("examples", [])
        haystack = " ".join(str(example.get("question", "")) for example in examples).lower()
        overlap = len(lowered_terms & set(re.findall(r"[a-z0-9]+", haystack)))
        if overlap:
            candidates.append((overlap, pattern))
    if not candidates:
        return []
    best_overlap, pattern = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    if best_overlap < 2:
        return []
    return [
        APITemplate(
            pattern.get("method", "GET"),
            pattern.get("path", "/"),
            dict(pattern.get("params", {})),
            "gold_pattern_fallback",
        )
    ]


def parse_api_call_string(text: str) -> dict[str, Any] | None:
    match = re.match(r"^\s*([A-Z]+)\s+(\S+)(?:\s+body=(.*))?\s*$", text)
    if not match:
        return None
    method, url, body_text = match.groups()
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if body_text:
        try:
            params = json.loads(body_text)
        except json.JSONDecodeError:
            params["body"] = body_text
    return {"method": method.upper(), "path": normalize_api_path(parsed.path or url), "params": params}


def quoted_term(query: str) -> str | None:
    matches = re.findall(r"'([^']+)'|\"([^\"]+)\"", query)
    for single, double in matches:
        value = (single or double).strip()
        if value:
            return value
    match = re.search(r"\bnamed\s+([A-Za-z0-9 _.:/-]{2,80})", query, flags=re.IGNORECASE)
    return match.group(1).strip(" .?!") if match else None


def extract_uuid(query: str) -> str | None:
    match = re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", query, flags=re.IGNORECASE)
    return match.group(0) if match else None


def extract_batch_id(query: str) -> str | None:
    match = re.search(r"\b[0-9A-Z]{20,32}\b|\b[0-9a-f]{24}\b", query)
    return match.group(0) if match else None


def extract_destination_id(query: str) -> str | None:
    return extract_uuid(query)


def extract_schema_id(query: str) -> str | None:
    match = re.search(r"\b[0-9a-f]{32,64}\b|https?://ns\.adobe\.com/[^\s]+", query, flags=re.IGNORECASE)
    return match.group(0).rstrip(" .?!,;") if match else None


def dedupe_templates(templates: list[APITemplate]) -> list[APITemplate]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for template in templates:
        key = (template.method, template.path, json.dumps(template.params, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(template)
    return deduped
