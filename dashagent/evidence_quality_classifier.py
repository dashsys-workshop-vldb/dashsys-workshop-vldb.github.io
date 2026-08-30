from __future__ import annotations

from typing import Any


def classify_evidence_quality(tool_results: list[dict[str, Any]], *, api_required: bool = False) -> dict[str, Any]:
    sql_codes: list[str] = []
    api_codes: list[str] = []
    conflict_codes: list[str] = []
    caveats: list[str] = []

    sql_results = [result for result in tool_results if result.get("type") == "sql"]
    api_results = [result for result in tool_results if result.get("type") == "api"]

    if not sql_results:
        sql_codes.append("SQL_NOT_RUN")
    for result in sql_results:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        if not payload.get("ok") or payload.get("error"):
            sql_codes.append("SQL_ERROR")
            continue
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        row_count = int(payload.get("row_count", len(rows)) or 0)
        if row_count == 0:
            sql_codes.append("SQL_ZERO_ROWS")
        elif _has_useful_fields(rows):
            sql_codes.append("SQL_DIRECT_ANSWER")
        else:
            sql_codes.append("SQL_NO_USEFUL_FIELDS")
        if row_count > 0 and _has_missing_like_marker(payload):
            sql_codes.append("SQL_PARTIAL")

    if not api_results:
        api_codes.append("API_NOT_RUN")
    for result in api_results:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
        state = str(parsed.get("evidence_state") or "").lower()
        if payload.get("dry_run"):
            api_codes.append("API_ERROR")
            caveats.append("api_error_is_unavailable_not_no_data")
            continue
        if not payload.get("ok") or payload.get("error") or state in {"api_error", "malformed_response"}:
            api_codes.append("API_ERROR")
            caveats.append("api_error_is_unavailable_not_no_data")
            continue
        if state == "live_empty" or _api_empty(payload, parsed):
            api_codes.append("API_LIVE_EMPTY")
            caveats.append("live_empty_is_scoped_not_global_no_data")
            continue
        if _api_has_direct_payload(payload, parsed):
            api_codes.append("API_DIRECT_ANSWER")
        elif parsed:
            api_codes.append("API_VERIFICATION_ONLY")
        else:
            api_codes.append("API_NO_USABLE_PAYLOAD")

    if "SQL_ZERO_ROWS" in sql_codes and "API_DIRECT_ANSWER" in api_codes:
        conflict_codes.append("SQL_ZERO_API_SUCCESS")
    if "SQL_DIRECT_ANSWER" in sql_codes and "API_LIVE_EMPTY" in api_codes:
        conflict_codes.append("SQL_SUCCESS_API_EMPTY")
    if "SQL_DIRECT_ANSWER" in sql_codes and "API_ERROR" in api_codes:
        conflict_codes.append("SQL_SUCCESS_API_ERROR")
    if api_required and "API_NOT_RUN" in api_codes:
        conflict_codes.append("REQUIRED_API_MISSING")
    if "SQL_DIRECT_ANSWER" in sql_codes and "API_VERIFICATION_ONLY" in api_codes:
        conflict_codes.append("OPTIONAL_API_NOISE")

    return {
        "sql": _dedupe(sql_codes),
        "api": _dedupe(api_codes),
        "conflict": _dedupe(conflict_codes),
        "caveats": _dedupe(caveats),
        "live_empty_scoped": "API_LIVE_EMPTY" in api_codes,
        "api_error_is_unavailable": "API_ERROR" in api_codes,
    }


def _has_useful_fields(rows: list[Any]) -> bool:
    if not rows:
        return False
    first = rows[0]
    return isinstance(first, dict) and any(value not in (None, "", [], {}) for value in first.values())


def _has_missing_like_marker(payload: dict[str, Any]) -> bool:
    missing = payload.get("missing_roles") or payload.get("missing_fields")
    return bool(missing)


def _api_empty(payload: dict[str, Any], parsed: dict[str, Any]) -> bool:
    if parsed.get("empty") is True:
        return True
    preview = payload.get("result_preview")
    return preview in ({}, [], "", None) and not _api_has_direct_payload(payload, parsed)


def _api_has_direct_payload(payload: dict[str, Any], parsed: dict[str, Any]) -> bool:
    if parsed.get("live_evidence_available") or parsed.get("usable_evidence"):
        return True
    for key in ("items", "ids", "names", "statuses"):
        value = parsed.get(key)
        if isinstance(value, list) and value:
            return True
    counts = parsed.get("counts")
    if isinstance(counts, dict) and any(value not in (None, "", [], {}) for value in counts.values()):
        return True
    preview = payload.get("result_preview")
    if isinstance(preview, dict) and preview:
        return True
    if isinstance(preview, list) and preview:
        return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
