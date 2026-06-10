from __future__ import annotations

from typing import Any

from .trajectory import redact_secrets


def build_sql_execution_evidence(sql: str, execution_result: dict[str, Any]) -> dict[str, Any]:
    rows = execution_result.get("rows") if isinstance(execution_result, dict) else []
    rows = rows if isinstance(rows, list) else []
    rows_preview = [_safe_preview_row(row) for row in rows[:5] if isinstance(row, dict)]
    columns = list(rows_preview[0].keys()) if rows_preview else []
    row_count = execution_result.get("row_count") if isinstance(execution_result, dict) else None
    evidence = {
        "sql_executed": bool(execution_result.get("ok")) if isinstance(execution_result, dict) else False,
        "sql": sql,
        "row_count": row_count,
        "columns": columns,
        "rows_preview": rows_preview,
        "count_value": _count_value(rows_preview),
        "key_ids": _values_by_column_kind(rows_preview, ("id",)),
        "key_names": _values_by_column_kind(rows_preview, ("name", "title", "display")),
        "status_values": _values_by_column_kind(rows_preview, ("status", "state")),
        "timestamp_values": _values_by_column_kind(rows_preview, ("time", "date", "created", "updated", "deployed", "published")),
        "zero_rows": bool(execution_result.get("ok")) and row_count == 0,
        "error": execution_result.get("error") if isinstance(execution_result, dict) else None,
    }
    return redact_secrets(evidence)


def _count_value(rows: list[dict[str, Any]]) -> Any:
    if not rows:
        return None
    row = rows[0]
    for key, value in row.items():
        normalized = key.lower()
        if normalized in {"count", "cnt", "total", "total_count"} or normalized.endswith("count"):
            return value
    return None


def _safe_preview_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not _sensitive_column(key)}


def _sensitive_column(column: str) -> bool:
    normalized = column.lower().replace("_", "")
    return any(marker in normalized for marker in ("imsorg", "orgid", "sandbox", "token", "secret", "apikey", "authorization"))


def _values_by_column_kind(rows: list[dict[str, Any]], markers: tuple[str, ...]) -> list[Any]:
    values = []
    seen = set()
    for row in rows:
        for key, value in row.items():
            normalized = key.lower()
            if value is None:
                continue
            if any(marker in normalized for marker in markers):
                text = str(value)
                if text not in seen:
                    seen.add(text)
                    values.append(value)
    return values
