from __future__ import annotations

from typing import Any

from .trajectory import compact_preview, redact_secrets


ID_FIELDS = {
    "id",
    "_id",
    "@id",
    "imsOrg",
    "imsOrgId",
    "datasetId",
    "flowId",
    "runId",
    "batchId",
    "segmentId",
    "audienceId",
    "destinationId",
    "schemaId",
    "tagId",
}
NAME_FIELDS = {"name", "title", "displayName", "label", "fileName", "filename"}
STATUS_FIELDS = {"status", "state", "enabled", "lifecycleState", "lifecycleStatus"}
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
    "timestamp",
    "time",
    "date",
}
COUNT_FIELDS = {
    "count",
    "total",
    "totalCount",
    "total_count",
    "size",
    "totalElements",
    "numElements",
    "resultsCount",
    "totalProfiles",
    "totalMembers",
}
COLLECTION_KEYS = (
    "items",
    "results",
    "data",
    "children",
    "entities",
    "resources",
    "records",
    "entry",
    "values",
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
    error: str | None = None,
    max_preview_chars: int = 1000,
) -> dict[str, Any]:
    """Normalize live Adobe API payloads into structured evidence.

    This parser is intentionally conservative: it extracts common evidence fields
    and keeps a redacted preview, but it never invents data when the API is dry-run
    or errored.
    """

    if dry_run:
        return {
            "ok": False,
            "dry_run": True,
            "live_evidence_available": False,
            "evidence_state": "dry_run_unavailable",
            "status_code": status_code,
            "endpoint": endpoint,
            "endpoint_id": endpoint_id,
            "endpoint_family": endpoint_family,
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

    errors = _extract_errors(raw)
    if error:
        errors.append(error)
    if not ok:
        return {
            "ok": False,
            "dry_run": False,
            "live_evidence_available": False,
            "evidence_state": "api_error",
            "status_code": status_code,
            "endpoint": endpoint,
            "endpoint_id": endpoint_id,
            "endpoint_family": endpoint_family,
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

    items = _extract_items(raw)
    ids: list[str] = []
    names: list[str] = []
    statuses: list[str] = []
    counts: dict[str, Any] = {}
    timestamps: dict[str, Any] = {}
    _collect_evidence(raw, ids=ids, names=names, statuses=statuses, counts=counts, timestamps=timestamps)
    if not counts and items:
        counts["items"] = len(items)

    evidence_state = "live_evidence" if items or ids or names or statuses or counts or timestamps else "live_empty_result"
    return {
        "ok": True,
        "dry_run": False,
        "live_evidence_available": evidence_state == "live_evidence",
        "evidence_state": evidence_state,
        "status_code": status_code,
        "endpoint": endpoint,
        "endpoint_id": endpoint_id,
        "endpoint_family": endpoint_family,
        "items": items,
        "ids": _dedupe(ids),
        "names": _dedupe(names),
        "statuses": _dedupe(statuses),
        "counts": counts,
        "timestamps": timestamps,
        "pagination": _extract_pagination(raw),
        "errors": [],
        "raw_preview": compact_preview(raw, max_preview_chars),
    }


def _extract_items(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [redact_secrets(item) for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []

    embedded = raw.get("_embedded")
    if isinstance(embedded, dict):
        nested = _extract_items(embedded)
        if nested:
            return nested

    for key in COLLECTION_KEYS:
        value = raw.get(key)
        if isinstance(value, list):
            return [redact_secrets(item) for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested

    dict_values = [value for value in raw.values() if isinstance(value, dict)]
    if dict_values and len(dict_values) == len(raw):
        return [redact_secrets(value) for value in dict_values]

    nested_collections = []
    for value in raw.values():
        if isinstance(value, dict):
            nested_collections.extend(_extract_items(value))
    if nested_collections:
        return nested_collections

    if raw and not any(isinstance(raw.get(key), (list, dict)) for key in COLLECTION_KEYS):
        return [redact_secrets(raw)]
    return []


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
    if depth > 4:
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
    for key in ("_links", "links"):
        value = raw.get(key)
        if isinstance(value, dict):
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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
