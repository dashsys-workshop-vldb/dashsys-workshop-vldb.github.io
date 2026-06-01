from __future__ import annotations

from typing import Any

from .trajectory import redact_secrets


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
        rows.append({"table": name, "columns": columns})
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
        path_params_raw = endpoint.get("path_params") if isinstance(endpoint.get("path_params"), list) else []
        rows.append(
            redact_secrets(
                {
                    "endpoint_id": endpoint_id,
                    "method": method,
                    "path": path,
                    "path_params": [str(item) for item in path_params_raw],
                    "query_params": [str(item) for item in query_params],
                    "description": str(endpoint.get("description") or endpoint.get("use_when") or "").strip(),
                }
            )
        )
    return rows
