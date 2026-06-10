from __future__ import annotations

import re
from typing import Any

from .trajectory import redact_secrets
from .v2_schema_grounding import table_aliases_for


def build_allowed_local_schema_card(schema_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a mechanical selectable schema card without semantic ranking."""
    tables = schema_context.get("tables") if isinstance(schema_context, dict) else None
    rows: list[dict[str, Any]] = []
    if isinstance(tables, dict):
        iterable = [{"name": name, **(meta if isinstance(meta, dict) else {})} for name, meta in tables.items()]
    elif isinstance(tables, list):
        iterable = [item for item in tables if isinstance(item, dict)]
    else:
        iterable = []
    for table in iterable:
        name = str(table.get("name") or table.get("table") or "").strip()
        if not name:
            continue
        columns_raw = table.get("columns") or table.get("fields") or []
        columns: list[str] = []
        if isinstance(columns_raw, dict):
            columns = [str(key).strip() for key in columns_raw if str(key).strip()]
        elif isinstance(columns_raw, list):
            for column in columns_raw:
                if isinstance(column, dict):
                    value = column.get("name") or column.get("column") or column.get("field")
                else:
                    value = column
                text = str(value or "").strip()
                if text:
                    columns.append(text)
        if table.get("load_error") or columns == ['__empty_parquet_placeholder']:
            continue
        rows.append(
            {
                "table": name,
                "columns": columns,
                "table_aliases": table_aliases_for(name),
                "table_role_hints": _table_role_hints(name, columns),
                "field_hints": _field_hints(columns),
            }
        )
    return rows


def build_allowed_api_context_card(endpoint_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a mechanical safe-GET API card; write endpoints are excluded."""
    rows: list[dict[str, Any]] = []
    for endpoint in endpoint_context:
        if not isinstance(endpoint, dict):
            continue
        method = str(endpoint.get("method") or "GET").strip().upper()
        if method != "GET":
            continue
        endpoint_id = str(endpoint.get("id") or endpoint.get("endpoint_id") or endpoint.get("path") or "").strip()
        path = str(endpoint.get("path") or "").strip()
        if not endpoint_id or not path:
            continue
        query_params_raw = endpoint.get("query_params")
        if isinstance(query_params_raw, dict):
            query_params = list(query_params_raw.keys())
        elif isinstance(query_params_raw, list):
            query_params = [str(item) for item in query_params_raw]
        else:
            common = endpoint.get("common_params") if isinstance(endpoint.get("common_params"), dict) else {}
            query_params = list(common.keys())
        common_params = endpoint.get("common_params") if isinstance(endpoint.get("common_params"), dict) else {}
        path_params_raw = endpoint.get("path_params") if isinstance(endpoint.get("path_params"), list) else []
        rows.append(
            redact_secrets(
                {
                    "endpoint_id": endpoint_id,
                    "method": method,
                    "path": path,
                    "path_params": [str(item) for item in path_params_raw],
                    "query_params": [str(item) for item in query_params],
                    "common_params": dict(common_params),
                    "domains": [str(item) for item in endpoint.get("domains", [])] if isinstance(endpoint.get("domains"), list) else [],
                    "examples": _compact_examples(endpoint.get("examples")),
                    "endpoint_role_hints": _endpoint_role_hints(endpoint_id, path, str(endpoint.get("description") or endpoint.get("use_when") or "")),
                    "description": str(endpoint.get("description") or endpoint.get("use_when") or "").strip(),
                }
            )
        )
    return rows


def _table_role_hints(table: str, columns: list[str]) -> list[str]:
    text = " ".join([table, *columns]).lower()
    hints: list[str] = []
    table_norm = table.lower()
    if table_norm == "dim_blueprint" or "blueprint" in table_norm:
        hints.extend(["schema", "blueprint", "xdm_schema"])
    if table_norm == "dim_segment" or "segment" in table_norm:
        hints.extend(["segment", "audience", "segment_definition"])
    if table_norm == "dim_campaign" or "campaign" in table_norm:
        hints.extend(["campaign", "journey"])
    mapping = [
        ("campaign", ["campaign", "journey"]),
        ("journey", ["journey", "campaign"]),
        ("blueprint", ["schema", "blueprint", "xdm_schema"]),
        ("schema", ["schema", "xdm_schema"]),
        ("segment", ["segment", "audience", "segment_definition"]),
        ("audience", ["audience", "segment"]),
        ("collection", ["dataset", "collection"]),
        ("dataset", ["dataset", "collection"]),
        ("connector", ["source", "connector", "dataflow"]),
        ("source", ["source", "connector", "dataflow"]),
        ("target", ["destination", "target"]),
        ("destination", ["destination", "target"]),
        ("property", ["field", "property"]),
        ("batch", ["batch"]),
        ("tag", ["tag"]),
        ("merge", ["merge_policy"]),
    ]
    for token, values in mapping:
        if token in text:
            hints.extend(values)
    if table.lower().startswith(("dim_", "fact_")):
        hints.append("snapshot_record_table")
    if table.lower().startswith(("br_", "hkg_br_")) or "_br_" in table.lower():
        hints.extend(["bridge_table", "relationship_table"])
    return _dedupe(hints)


def _field_hints(columns: list[str]) -> dict[str, list[str]]:
    label_fields = [column for column in columns if _norm(column).startswith("labels") or "semanticlabel" in _norm(column)]
    primary_name_fields = [
        column
        for column in columns
        if (
            _norm(column) in {"name", "displayname", "title", "altid"}
            or ("name" in _norm(column) and _norm(column) not in {"sandboxname", "imsorgname"})
            or "title" in _norm(column)
            or _norm(column) in {"label"}
            or "displayname" in _norm(column)
        )
        and column not in label_fields
    ]
    status_tokens = {"status", "state", "lifecyclestatus", "lifecycle_status", "enabled", "active"}
    return {
        "id_fields": [column for column in columns if _norm(column).endswith("id") or "_id" in str(column).lower() or _norm(column) == "id"],
        "name_fields": [
            column
            for column in columns
            if (
                "name" in _norm(column)
                or "title" in _norm(column)
                or "label" in _norm(column)
                or "displayname" in _norm(column)
                or "altid" in _norm(column)
            )
        ],
        "primary_name_fields": primary_name_fields,
        "label_fields": label_fields,
        "entity_lookup_fields": [*primary_name_fields, *label_fields],
        "status_fields": [
            column
            for column in columns
            if _norm(column) in status_tokens or "status" in _norm(column) or "state" in _norm(column)
        ],
        "date_fields": [
            column
            for column in columns
            if _looks_like_date_field(column)
        ],
        "count_fields": [column for column in columns if "count" in _norm(column) or _norm(column) in {"total", "rowcount"}],
    }


def _endpoint_role_hints(endpoint_id: str, path: str, description: str) -> list[str]:
    text = " ".join([endpoint_id, path, description]).lower()
    hints: list[str] = []
    mapping = [
        ("schema", ["schema_registry", "schema", "live_api"]),
        ("journey", ["journey", "campaign", "live_api"]),
        ("audience", ["audience", "segment", "live_api"]),
        ("segment", ["segment_definition", "segment_job", "live_api"]),
        ("flow", ["destination", "dataflow", "live_api"]),
        ("run", ["dataflow_run", "status", "live_api"]),
        ("audit", ["recent_changes", "audit_events", "live_api"]),
        ("tag", ["tag", "live_api"]),
        ("merge", ["merge_policy", "live_api"]),
        ("batch", ["batch", "live_api"]),
        ("file", ["batch_file", "download", "live_api"]),
    ]
    for token, values in mapping:
        if token in text:
            hints.extend(values)
    return _dedupe(hints)


def _compact_examples(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    examples: list[dict[str, Any]] = []
    for item in value[:3]:
        if isinstance(item, dict):
            examples.append({str(key): item[key] for key in list(item)[:4]})
    return examples


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(value).lower())


def _looks_like_date_field(column: str) -> bool:
    norm = _norm(column)
    if norm.endswith("id") or norm.endswith("by") or "clientid" in norm or "orgid" in norm:
        return False
    return any(
        token in norm
        for token in ["time", "date", "created", "updated", "modified", "published", "deployed", "finished", "stopped", "start", "end"]
    )


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
