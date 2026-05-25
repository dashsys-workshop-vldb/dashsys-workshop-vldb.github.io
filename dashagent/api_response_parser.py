from __future__ import annotations

from typing import Any

from .endpoint_catalog import normalize_api_path
from .trajectory import compact_preview, redact_secrets


ID_FIELDS = {
    "id",
    "_id",
    "@id",
    "uuid",
    "uid",
    "imsOrg",
    "imsOrgId",
    "datasetId",
    "flowId",
    "runId",
    "batchId",
    "batch_id",
    "segmentId",
    "audienceId",
    "destinationId",
    "schemaId",
    "schema_id",
    "tagId",
    "tag_id",
    "journeyId",
    "campaignId",
    "policyId",
    "eventId",
}
NAME_FIELDS = {"name", "title", "displayName", "label", "fileName", "filename", "metric"}
STATUS_FIELDS = {
    "status",
    "state",
    "enabled",
    "lifecycleState",
    "lifecycleStatus",
    "runStatus",
    "healthStatus",
    "isDefault",
    "default",
}
TIMESTAMP_FIELDS = {
    "created",
    "createdAt",
    "createdTime",
    "createTime",
    "updated",
    "updatedAt",
    "updatedTime",
    "updateTime",
    "modified",
    "modifiedTime",
    "lastModified",
    "publishedAt",
    "publishedTime",
    "startedAt",
    "startTime",
    "completedAt",
    "completedTime",
    "timestamp",
    "time",
    "date",
    "windowStart",
    "windowEnd",
}
COUNT_FIELDS = {
    "count",
    "total",
    "totalCount",
    "totalResults",
    "total_count",
    "size",
    "totalElements",
    "numElements",
    "resultsCount",
    "totalProfiles",
    "totalMembers",
    "value",
}
COLLECTION_KEYS = (
    "items",
    "results",
    "data",
    "dataSets",
    "datasets",
    "children",
    "entities",
    "resources",
    "records",
    "entry",
    "values",
    "journeys",
    "audiences",
    "segments",
    "segmentDefinitions",
    "definitions",
    "flows",
    "runs",
    "dataFlows",
    "schemas",
    "tags",
    "tagCategories",
    "categories",
    "mergePolicies",
    "policies",
    "jobs",
    "segmentJobs",
    "batches",
    "batch",
    "files",
    "failed",
    "events",
    "metrics",
    "series",
)
PAGINATION_KEYS = (
    "_page",
    "page",
    "meta",
    "pagination",
    "links",
    "next",
    "start",
    "limit",
    "total",
    "count",
    "totalCount",
    "totalResults",
    "_links",
)


FAMILY_ITEM_KEYS: dict[str, tuple[str, ...]] = {
    "journey_list": ("items", "journeys", "results", "data", "children", "entities", "resources"),
    "ups_audiences": ("items", "audiences", "results", "children", "entities", "data", "resources"),
    "segment_definitions": ("items", "segmentDefinitions", "definitions", "segments", "results", "children", "entities", "data"),
    "flowservice_flows": ("items", "flows", "dataFlows", "results", "entities", "data", "resources"),
    "flowservice_runs": ("items", "runs", "results", "entities", "data", "resources"),
    "catalog_datasets": ("items", "dataSets", "datasets", "results", "entities", "data", "resources"),
    "schema_registry_schemas": ("items", "schemas", "results", "children", "entities", "data", "resources"),
    "schema_registry_schema": ("items", "schemas", "results", "children", "entities", "data", "resources"),
    "schemas_short": ("items", "schemas", "results", "children", "entities", "data", "resources"),
    "unified_tags": ("items", "tags", "results", "children", "entities", "data", "resources"),
    "unified_tag_categories": ("items", "tagCategories", "categories", "results", "children", "entities", "data"),
    "unified_tag_detail": ("items", "tags", "results", "children", "entities", "data", "resources"),
    "merge_policies": ("items", "mergePolicies", "policies", "results", "children", "entities", "data"),
    "segment_jobs": ("items", "jobs", "segmentJobs", "evaluations", "results", "children", "entities", "data"),
    "catalog_batches": ("items", "batches", "batch", "results", "children", "entities", "data"),
    "catalog_batch_detail": ("items", "batches", "batch", "results", "children", "entities", "data"),
    "export_batch_files": ("items", "files", "results", "children", "entities", "data"),
    "export_batch_failed": ("items", "files", "failed", "results", "children", "entities", "data"),
    "audit_events": ("items", "events", "results", "entities", "data", "resources"),
    "audit_events_short": ("items", "events", "results", "entities", "data", "resources"),
    "observability_metrics": ("items", "metrics", "series", "results", "entities", "data", "resources"),
}


PATH_FAMILY_HINTS = (
    ("journey", "journey_list"),
    ("ups/audiences", "ups_audiences"),
    ("segment/definitions", "segment_definitions"),
    ("flowservice/flows", "flowservice_flows"),
    ("flowservice/runs", "flowservice_runs"),
    ("catalog/dataSets", "catalog_datasets"),
    ("schemaregistry/tenant/schemas/", "schema_registry_schema"),
    ("schemaregistry/tenant/schemas", "schema_registry_schemas"),
    ("/schemas", "schemas_short"),
    ("unifiedtags/tagCategory", "unified_tag_categories"),
    ("unifiedtags/tags/", "unified_tag_detail"),
    ("unifiedtags/tags", "unified_tags"),
    ("mergePolicies", "merge_policies"),
    ("segment/jobs", "segment_jobs"),
    ("catalog/batches/", "catalog_batch_detail"),
    ("catalog/batches", "catalog_batches"),
    ("export/batches", "export_batch_files"),
    ("audit/events", "audit_events"),
    ("observability", "observability_metrics"),
)


def normalize_api_response(
    raw: Any,
    *,
    ok: bool,
    dry_run: bool,
    status_code: int | None = None,
    endpoint: str | None = None,
    endpoint_id: str | None = None,
    endpoint_family: str | None = None,
    method: str | None = None,
    path: str | None = None,
    error: str | None = None,
    error_category: str | None = None,
    malformed_response: bool = False,
    max_preview_chars: int = 1000,
) -> dict[str, Any]:
    """Normalize Adobe API payloads into safe structured evidence."""

    normalized_path = normalize_api_path(path or endpoint or "") if (path or endpoint) else None
    family = endpoint_family or endpoint_id or _family_from_path(normalized_path)
    identity = {
        "status_code": status_code,
        "endpoint": normalized_path,
        "endpoint_id": endpoint_id,
        "endpoint_family": family,
        "method": method.upper() if method else None,
        "path": normalized_path,
    }

    if dry_run:
        return {
            **identity,
            "ok": False,
            "dry_run": True,
            "live_evidence_available": False,
            "evidence_state": "dry_run_unavailable",
            "error_category": "dry_run_unavailable",
            "parser_mode": "dry_run_unavailable",
            "items": [],
            "ids": [],
            "names": [],
            "statuses": [],
            "counts": {},
            "timestamps": {},
            "pagination": {},
            "errors": [error or "dry_run_unavailable"],
            "raw_preview": None,
        }

    if malformed_response:
        return {
            **identity,
            "ok": False,
            "dry_run": False,
            "live_evidence_available": False,
            "evidence_state": "malformed_response",
            "error_category": "malformed_response",
            "parser_mode": "malformed_response",
            "items": [],
            "ids": [],
            "names": [],
            "statuses": [],
            "counts": {},
            "timestamps": {},
            "pagination": {},
            "errors": [error or "malformed_response"],
            "raw_preview": compact_preview(raw, max_preview_chars),
        }

    errors = _extract_errors(raw)
    if error:
        errors.append(error)
    if not ok:
        state = error_category or "api_error"
        return {
            **identity,
            "ok": False,
            "dry_run": False,
            "live_evidence_available": False,
            "evidence_state": state,
            "error_category": state,
            "parser_mode": state,
            "items": [],
            "ids": [],
            "names": [],
            "statuses": [],
            "counts": {},
            "timestamps": {},
            "pagination": _extract_pagination(raw),
            "errors": _dedupe([str(item)[:500] for item in errors]) or ["api_error"],
            "raw_preview": compact_preview(raw, max_preview_chars),
        }

    generic_items = _extract_items(raw)
    family_items = _extract_items_for_family(raw, family)
    family_empty_collection = _has_family_collection(raw, family)
    items = family_items if family_items or family_empty_collection else generic_items
    parser_mode = "endpoint_family" if family and family_items else ("generic" if generic_items else "generic_fallback")

    ids: list[str] = []
    names: list[str] = []
    statuses: list[str] = []
    counts: dict[str, Any] = {}
    timestamps: dict[str, Any] = {}
    _collect_evidence(raw, ids=ids, names=names, statuses=statuses, counts=counts, timestamps=timestamps)
    family_fields = _collect_family_fields(family, items, raw)
    ids.extend(family_fields.pop("ids", []))
    names.extend(family_fields.pop("names", []))
    statuses.extend(family_fields.pop("statuses", []))
    timestamps.update(family_fields.pop("timestamps", {}))
    counts.update({key: value for key, value in family_fields.pop("counts", {}).items() if key not in counts})
    if not counts and items:
        counts["items"] = len(items)

    counts_are_evidence = any(not _is_zero_count(value) for value in counts.values())
    evidence_state = "live_evidence" if items or ids or names or statuses or timestamps or counts_are_evidence else "live_empty"
    important_fields = {
        "ids": _dedupe(ids)[:10],
        "names": _dedupe(names)[:10],
        "statuses": _dedupe(statuses)[:10],
        "counts": counts,
        "timestamps": timestamps,
        **family_fields,
    }
    important_fields = {key: value for key, value in important_fields.items() if value not in ([], {}, None, "")}
    return {
        **identity,
        "ok": True,
        "dry_run": False,
        "live_evidence_available": evidence_state == "live_evidence",
        "evidence_state": evidence_state,
        "error_category": None,
        "parser_mode": parser_mode,
        "items": items,
        "ids": _dedupe(ids),
        "names": _dedupe(names),
        "statuses": _dedupe(statuses),
        "counts": counts,
        "timestamps": timestamps,
        "pagination": _extract_pagination(raw),
        "errors": [],
        "important_fields": redact_secrets(important_fields),
        "raw_preview": compact_preview(raw, max_preview_chars),
    }


def _family_from_path(path: str | None) -> str | None:
    if not path:
        return None
    lowered = path.lower()
    for marker, family in PATH_FAMILY_HINTS:
        if marker.lower() in lowered:
            return family
    return None


def _extract_items_for_family(raw: Any, family: str | None) -> list[dict[str, Any]]:
    if not family:
        return []
    return _extract_items_with_keys(raw, FAMILY_ITEM_KEYS.get(family, ()))


def _has_family_collection(raw: Any, family: str | None) -> bool:
    if not family or not isinstance(raw, dict):
        return False
    for key in FAMILY_ITEM_KEYS.get(family, ()):
        value = raw.get(key)
        if isinstance(value, (list, dict)):
            return True
    embedded = raw.get("_embedded")
    if isinstance(embedded, dict):
        return _has_family_collection(embedded, family)
    return False


def _extract_items(raw: Any) -> list[dict[str, Any]]:
    return _extract_items_with_keys(raw, COLLECTION_KEYS)


def _extract_items_with_keys(raw: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [redact_secrets(item) for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []

    embedded = raw.get("_embedded")
    if isinstance(embedded, dict):
        nested = _extract_items_with_keys(embedded, keys)
        if nested:
            return nested

    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return [redact_secrets(item) for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items_with_keys(value, keys)
            if nested:
                return nested

    for key in ("entry", "record", "value", "payload"):
        value = raw.get(key)
        if isinstance(value, dict):
            nested = _extract_items_with_keys(value, keys)
            if nested:
                return nested

    dict_values = [value for value in raw.values() if isinstance(value, dict)]
    if dict_values and len(dict_values) == len(raw):
        return [redact_secrets(value) for value in dict_values]

    nested_collections = []
    for value in raw.values():
        if isinstance(value, dict):
            nested_collections.extend(_extract_items_with_keys(value, keys))
    if nested_collections:
        return nested_collections

    if raw and not any(isinstance(raw.get(key), (list, dict)) for key in keys):
        return [redact_secrets(raw)]
    return []


def _collect_family_fields(family: str | None, items: list[dict[str, Any]], raw: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"ids": [], "names": [], "statuses": [], "counts": {}, "timestamps": {}}
    for item in items[:100]:
        _collect_by_aliases(item, fields)
        if family == "flowservice_flows":
            source = _first_value(item, ("sourceConnectionId", "sourceConnectionIds", "sourceId"))
            destination = _first_value(item, ("destinationConnectionId", "destinationConnectionIds", "destinationId"))
            if source is not None:
                fields.setdefault("source_connection_ids", []).append(str(source))
            if destination is not None:
                fields.setdefault("destination_connection_ids", []).append(str(destination))
        elif family == "flowservice_runs":
            err = _first_value(item, ("error", "errors", "errorInfo", "failureReason"))
            if err is not None:
                fields.setdefault("error_info", []).append(str(compact_preview(err, 300)))
        elif family in {"catalog_datasets"}:
            schema_ref = _first_value(item, ("schemaRef", "schema", "schemaId", "schema_id"))
            if schema_ref is not None:
                fields.setdefault("schema_refs", []).append(str(compact_preview(schema_ref, 300)))
        elif family in {"schema_registry_schemas", "schema_registry_schema", "schemas_short"}:
            version = _first_value(item, ("version", "schemaVersion", "_etag"))
            profile = _first_value(item, ("isProfileEnabled", "profileEnabled", "profile"))
            if version is not None:
                fields.setdefault("versions", []).append(str(version))
            if profile is not None:
                fields.setdefault("profile_enabled", []).append(profile)
        elif family in {"unified_tags", "unified_tag_categories", "unified_tag_detail"}:
            category = _first_value(item, ("category", "categoryId", "tagCategoryId", "tagCategoryName"))
            if category is not None:
                fields.setdefault("categories", []).append(str(compact_preview(category, 300)))
        elif family == "merge_policies":
            default = _first_value(item, ("isDefault", "default", "is_default"))
            schema = _first_value(item, ("schema", "schemaRef", "schemaName"))
            if default is not None:
                fields.setdefault("defaults", []).append(default)
            if schema is not None:
                fields.setdefault("schemas", []).append(str(compact_preview(schema, 300)))
        elif family in {"catalog_batches", "catalog_batch_detail"}:
            dataset = _first_value(item, ("datasetId", "dataSetId", "dataset", "dataSet"))
            if dataset is not None:
                fields.setdefault("dataset_ids", []).append(str(compact_preview(dataset, 300)))
        elif family in {"audit_events", "audit_events_short"}:
            actor = _first_value(item, ("actor", "user", "userName", "imsUserId"))
            action = _first_value(item, ("action", "eventType", "operation"))
            entity_type = _first_value(item, ("assetType", "entityType", "resourceType"))
            entity_id = _first_value(item, ("assetId", "entityId", "resourceId"))
            if actor is not None:
                fields.setdefault("actors", []).append(str(compact_preview(actor, 300)))
            if action is not None:
                fields.setdefault("actions", []).append(str(action))
            if entity_type is not None:
                fields.setdefault("entity_types", []).append(str(entity_type))
            if entity_id is not None:
                fields.setdefault("entity_ids", []).append(str(entity_id))
        elif family == "observability_metrics":
            metric = _first_value(item, ("metric", "name", "metricName"))
            value = _first_value(item, ("value", "count", "sum", "total"))
            if metric is not None:
                fields.setdefault("metric_names", []).append(str(metric))
            if value is not None:
                fields["counts"].setdefault(str(metric or "value"), _coerce_number(value))
    if family == "observability_metrics":
        values = _extract_observability_values(raw)
        if values:
            fields["values"] = values[:100]

    _collect_evidence(raw, ids=fields["ids"], names=fields["names"], statuses=fields["statuses"], counts=fields["counts"], timestamps=fields["timestamps"])
    for key, value in list(fields.items()):
        if key == "values":
            continue
        if isinstance(value, list):
            fields[key] = _dedupe([str(item) for item in value])
    return fields


def _extract_observability_values(raw: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []

    def visit(obj: Any, metric_name: Any = None) -> None:
        if isinstance(obj, list):
            for item in obj:
                visit(item, metric_name)
            return
        if not isinstance(obj, dict):
            return
        current_metric = obj.get("metric") or obj.get("name") or obj.get("metricName") or metric_name
        dps = obj.get("dps")
        if isinstance(dps, dict):
            for timestamp, value in dps.items():
                if timestamp == "truncated_fields":
                    continue
                values.append(
                    {
                        "metric": str(current_metric) if current_metric is not None else None,
                        "timestamp": str(timestamp),
                        "value": _coerce_number(value),
                    }
                )
        for key in ("metricResponses", "datapoints", "points", "values", "data", "series", "items", "results"):
            child = obj.get(key)
            if isinstance(child, (dict, list)):
                visit(child, current_metric)
        for child in obj.values():
            if isinstance(child, (dict, list)) and child is not dps:
                visit(child, current_metric)

    visit(raw)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        key = (str(item.get("metric")), str(item.get("timestamp")), str(item.get("value")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({key: value for key, value in item.items() if value is not None})
    return deduped


def _collect_by_aliases(item: dict[str, Any], fields: dict[str, Any]) -> None:
    _collect_evidence(item, ids=fields["ids"], names=fields["names"], statuses=fields["statuses"], counts=fields["counts"], timestamps=fields["timestamps"])


def _first_value(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _collect_evidence(
    raw: Any,
    *,
    ids: list[str],
    names: list[str],
    statuses: list[str],
    counts: dict[str, Any],
    timestamps: dict[str, Any],
    depth: int = 0,
) -> None:
    if depth > 5:
        return
    if isinstance(raw, list):
        for item in raw[:100]:
            _collect_evidence(item, ids=ids, names=names, statuses=statuses, counts=counts, timestamps=timestamps, depth=depth + 1)
        return
    if not isinstance(raw, dict):
        return

    for key, value in raw.items():
        if value in (None, "", [], {}):
            continue
        if key in ID_FIELDS and _scalar(value):
            ids.append(str(value))
        elif key in NAME_FIELDS and _scalar(value):
            names.append(str(value))
        elif key in STATUS_FIELDS and _scalar(value):
            statuses.append(str(value))
        elif key in COUNT_FIELDS and _number_like(value):
            counts.setdefault(key, _coerce_number(value))
        elif key in TIMESTAMP_FIELDS and _scalar(value):
            timestamps.setdefault(key, str(value))

        if isinstance(value, (dict, list)):
            _collect_evidence(value, ids=ids, names=names, statuses=statuses, counts=counts, timestamps=timestamps, depth=depth + 1)


def _extract_pagination(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    pagination: dict[str, Any] = {}
    for key in PAGINATION_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            pagination[key] = value
        elif isinstance(value, dict):
            pagination[key] = compact_preview(value, 600)
    return redact_secrets(pagination)


def _extract_errors(raw: Any) -> list[str]:
    errors: list[str] = []
    if isinstance(raw, dict):
        for key in ("error", "errors", "message", "detail", "title", "type"):
            value = raw.get(key)
            if not value:
                continue
            if isinstance(value, list):
                errors.extend(str(item) for item in value[:5])
            elif isinstance(value, dict):
                errors.append(str(compact_preview(value, 500)))
            else:
                errors.append(str(value))
    elif isinstance(raw, str) and raw:
        errors.append(raw[:500])
    return errors


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _number_like(value: Any) -> bool:
    return isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().replace(".", "", 1).isdigit())


def _coerce_number(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return value


def _is_zero_count(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return float(value) == 0.0
    if isinstance(value, str):
        try:
            return float(value.strip()) == 0.0
        except ValueError:
            return False
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
