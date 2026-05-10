from __future__ import annotations

from typing import Any


def normalize_api_evidence(family: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("result_preview")
    if payload.get("dry_run"):
        return {"items": [], "count": 0, "important_fields": {}, "empty": True, "errors": ["dry_run"]}
    if not payload.get("ok"):
        return {"items": [], "count": 0, "important_fields": {}, "empty": True, "errors": [payload.get("error") or "api_error"]}
    return parse_family_response(family, raw)


def parse_family_response(family: str, raw: Any) -> dict[str, Any]:
    if family in {"journey_by_name", "journey_default", "journey_inactive", "journey_list"}:
        return parse_items(raw, ["items", "journeys", "results", "data", "children", "entities", "resources"])
    if family == "merge_policies":
        return parse_merge_policies(raw)
    if family in {"segment_definition_count", "segment_definition_list", "recent_segment_definitions"}:
        return parse_items(raw, ["children", "items", "segments", "segmentDefinitions", "definitions", "results", "entities", "data", "resources"])
    if family == "segment_jobs":
        return parse_items(raw, ["children", "items", "jobs", "segmentJobs", "evaluations", "results", "entities", "data", "resources"])
    if family in {"tag_categories", "tag_count", "tag_details_by_id", "tag_list", "tags_by_uncategorized_category"}:
        return parse_items(raw, ["children", "items", "tags", "tagCategories", "categories", "results", "entities", "data", "resources"])
    if family in {"destination_flows", "failed_dataflow_flows", "recent_destination_flows"}:
        return parse_items(raw, ["items", "flows", "runs", "dataFlows", "results", "entities", "data", "resources"])
    if family in {"batch_details", "batch_export_files", "batch_list", "recent_batches", "successful_batch_count"}:
        return parse_items(raw, ["children", "items", "batches", "batch", "files", "results", "entities", "data", "resources"])
    if family == "observability_metrics":
        return parse_observability(raw)
    if family in {"audit_create_events", "audit_events", "dataset_audit_changes", "destination_audit_events"}:
        return parse_items(raw, ["events", "items", "results", "entities", "data", "resources"])
    return parse_items(raw, ["items", "children", "results", "entities", "data", "resources"])


def parse_items(raw: Any, keys: list[str]) -> dict[str, Any]:
    items = extract_items(raw, keys)
    count = extract_count(raw, items)
    important = first_important_fields(items[0]) if items else {}
    return {"items": items, "count": count, "important_fields": important, "empty": not items and count == 0, "errors": []}


def parse_merge_policies(raw: Any) -> dict[str, Any]:
    evidence = parse_items(raw, ["children", "items", "mergePolicies", "policies", "results", "entities", "data", "resources"])
    default = None
    for item in evidence["items"]:
        if truthy(item.get("isDefault")) or truthy(item.get("default")) or truthy(item.get("is_default")):
            default = item
            break
    if default is None and evidence["items"]:
        default = evidence["items"][0]
    if default:
        evidence["important_fields"] = first_important_fields(default)
        evidence["important_fields"]["default_policy_name"] = default.get("name") or default.get("title")
    return evidence


def parse_observability(raw: Any) -> dict[str, Any]:
    evidence = parse_items(raw, ["series", "items", "metrics", "results", "entities", "data"])
    values = extract_observability_values(evidence["items"])
    evidence["important_fields"] = {"values": values[:5]} if values else evidence["important_fields"]
    return evidence


def extract_items(raw: Any, keys: list[str]) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        embedded = raw.get("_embedded")
        if isinstance(embedded, dict):
            nested = extract_items(embedded, keys)
            if nested:
                return nested
        for key in keys:
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = extract_items(value, keys)
                if nested:
                    return nested
        for key in ["entry", "record", "value", "payload"]:
            value = raw.get(key)
            if isinstance(value, dict):
                nested = extract_items(value, keys)
                if nested:
                    return nested
        list_like_values = [value for value in raw.values() if isinstance(value, dict)]
        if list_like_values and len(list_like_values) == len(raw):
            return [value for value in list_like_values if isinstance(value, dict)]
        if raw and not any(isinstance(raw.get(key), (list, dict)) for key in keys):
            return [raw]
    return []


def extract_count(raw: Any, items: list[dict[str, Any]]) -> int:
    if isinstance(raw, dict):
        for key in ["total", "count", "totalCount", "total_count", "size", "totalElements", "numElements", "resultsCount"]:
            value = raw.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        for key in ["_page", "page", "meta", "pagination"]:
            value = raw.get(key)
            if isinstance(value, dict):
                nested = extract_count(value, items)
                if nested != len(items) or nested:
                    return nested
    return len(items)


def first_important_fields(item: dict[str, Any]) -> dict[str, Any]:
    important = {}
    for key in [
        "id",
        "_id",
        "@id",
        "name",
        "title",
        "status",
        "state",
        "schema",
        "schemaRef",
        "sandboxName",
        "created",
        "createdTime",
        "createTime",
        "updated",
        "updatedTime",
        "updateTime",
        "modified",
        "tagCategoryId",
        "category",
        "imsOrg",
        "imsOrgId",
        "runId",
        "flowId",
        "batchId",
        "fileName",
    ]:
        if key in item:
            important[key] = item[key]
    return important


def extract_observability_values(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in items:
        metric_name = item.get("metric") or item.get("name")
        points = None
        for key in ["points", "values", "data", "series"]:
            candidate = item.get(key)
            if isinstance(candidate, list):
                points = candidate
                break
        if points:
            for point in points:
                if not isinstance(point, dict):
                    continue
                normalized = normalize_observability_point(point, metric_name)
                if normalized:
                    values.append(normalized)
        else:
            normalized = normalize_observability_point(item, metric_name)
            if normalized:
                values.append(normalized)
    return values


def normalize_observability_point(point: dict[str, Any], metric_name: Any = None) -> dict[str, Any]:
    timestamp = (
        point.get("timestamp")
        or point.get("date")
        or point.get("time")
        or point.get("start")
        or point.get("startTime")
    )
    value = point.get("value")
    if value is None:
        value = point.get("count")
    if value is None:
        value = point.get("sum")
    if timestamp is None and value is None:
        return {}
    normalized = {}
    if metric_name is not None:
        normalized["metric"] = metric_name
    if timestamp is not None:
        normalized["timestamp"] = timestamp
    if value is not None:
        normalized["value"] = value
    return normalized


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)
