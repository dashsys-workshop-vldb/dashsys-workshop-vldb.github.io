from __future__ import annotations

from typing import Any

from .answer_claims import extract_claims
from .trajectory import redact_secrets


def ground_sql_result_answer(
    prompt: str,
    answer: str,
    sql_execution_result: dict[str, Any],
    *,
    answer_intent: str | None = None,
) -> dict[str, Any]:
    rows = sql_execution_result.get("rows") if isinstance(sql_execution_result, dict) else []
    rows = rows if isinstance(rows, list) else []
    row_count = sql_execution_result.get("row_count") if isinstance(sql_execution_result, dict) else None
    supported = _supported_values(rows, row_count)
    used = bool(answer and any(value and value.lower() in answer.lower() for value in supported))
    fallback = False
    grounded = answer or ""
    if sql_execution_result.get("ok") and not used:
        fallback = True
        grounded = _fallback_sql_answer(rows, row_count, answer_intent)
        supported = _supported_values(rows, row_count)
        used = bool(grounded)
    unsupported = _unsupported_claims(grounded, supported)
    if unsupported:
        fallback = True
        grounded = _fallback_sql_answer(rows, row_count, answer_intent)
        unsupported = _unsupported_claims(grounded, supported)
        used = True
    return redact_secrets(
        {
            "answer": grounded,
            "sql_result_used_in_answer": used,
            "fallback_to_sql_result_answer": fallback,
            "unsupported_claim_count": len(unsupported),
            "unsupported_claims": unsupported,
            "row_count": row_count,
        }
    )


def _fallback_sql_answer(rows: list[Any], row_count: Any, answer_intent: str | None) -> str:
    if row_count == 0 or rows == []:
        return "The SQL evidence returned no matching records for this request."
    if answer_intent == "COUNT" and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("count", "COUNT(*)", "cnt", "total"):
                if key in row:
                    return f"The SQL evidence reports {row[key]}."
    if rows:
        selected = [_compact_row(row) for row in rows[:5] if isinstance(row, dict)]
        return f"The SQL evidence returned {len(rows)} row(s): {selected}."
    if row_count is not None:
        return f"The SQL evidence returned {row_count} row(s)."
    return "The SQL evidence executed successfully, but no compact row values were available."


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    priority = {}
    for key, value in row.items():
        normalized = key.lower()
        if any(marker in normalized for marker in ("id", "name", "status", "state", "time", "date", "count", "total")):
            priority[key] = value
    return priority or dict(list(row.items())[:4])


def _supported_values(rows: list[Any], row_count: Any) -> set[str]:
    values: set[str] = set()
    if row_count is not None:
        values.add(str(row_count))
    for row in rows:
        _walk(row, values)
    for phrase in ("SQL evidence", "row", "rows", "matching records", "no matching records", "returned no"):
        values.add(phrase)
        values.add(phrase.lower())
    return values


def _walk(value: Any, values: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, (str, int, float, bool)):
        text = str(value)
        values.add(text)
        values.add(text.lower())
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            values.add(str(key))
            values.add(str(key).lower())
            _walk(nested, values)
        return
    if isinstance(value, list):
        for item in value:
            _walk(item, values)


def _unsupported_claims(answer: str, supported_values: set[str]) -> list[dict[str, str]]:
    unsupported = []
    for claim in extract_claims(answer):
        value = str(claim.value).strip()
        if not value:
            continue
        if value.lower() not in {item.lower() for item in supported_values}:
            unsupported.append({"claim_type": claim.claim_type, "value": value})
    return unsupported
