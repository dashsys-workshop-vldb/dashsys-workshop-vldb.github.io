from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .answer_reranker import select_best_answer
from .answer_templates import render_answer_template


@dataclass
class AnswerResult:
    answer: str
    diagnostics: dict[str, Any]


def synthesize_answer(query: str, tool_results: list[dict[str, Any]]) -> str:
    return synthesize_answer_with_diagnostics(query, tool_results).answer


def synthesize_answer_with_diagnostics(query: str, tool_results: list[dict[str, Any]]) -> AnswerResult:
    base_answer = synthesize_base_answer(query, tool_results)
    selection = select_best_answer(query, tool_results, base_answer)
    return AnswerResult(answer=selection.answer, diagnostics=selection.diagnostics)


def synthesize_base_answer(query: str, tool_results: list[dict[str, Any]]) -> str:
    sql_results = [result for result in tool_results if result.get("type") == "sql"]
    api_results = [result for result in tool_results if result.get("type") == "api"]

    templated = render_answer_template(query, sql_results, api_results)
    if templated:
        return templated

    sql_answer = summarize_sql(sql_results)
    api_answer = summarize_api(api_results)

    if sql_answer and api_answer:
        if any(result.get("payload", {}).get("dry_run") for result in api_results):
            return f"{sql_answer} Live API verification was not executed because Adobe credentials are unavailable."
        return f"{sql_answer} API evidence: {api_answer}"
    if sql_answer:
        return sql_answer
    if api_answer:
        return api_answer

    errors = [
        result.get("payload", {}).get("error")
        for result in tool_results
        if result.get("payload", {}).get("error")
    ]
    if errors:
        return f"Not found. The available tool evidence produced errors: {errors[0]}"
    return "Not found in the available SQL/API evidence."


def summarize_sql(sql_results: list[dict[str, Any]]) -> str | None:
    for result in sql_results:
        payload = result.get("payload", {})
        if not payload.get("ok"):
            continue
        rows = payload.get("rows") or []
        if not rows:
            return "The database query returned no matching rows."
        first = rows[0]
        if len(first) == 1 and "count" in {key.lower() for key in first}:
            value = next(iter(first.values()))
            return f"The database count is {value}."
        formatted = format_rows(rows)
        row_count = payload.get("row_count", len(rows))
        suffix = " The result may be truncated by the row limit." if payload.get("limited") else ""
        return f"The database returned {row_count} matching row(s): {formatted}.{suffix}"
    return None


def summarize_api(api_results: list[dict[str, Any]]) -> str | None:
    for result in api_results:
        payload = result.get("payload", {})
        if payload.get("dry_run"):
            return "Live API verification was skipped because Adobe credentials are unavailable."
        if not payload.get("ok"):
            error = payload.get("error") or "unknown API error"
            return f"API call failed or returned no usable evidence ({error})."
        preview = payload.get("result_preview")
        if preview in (None, "", [], {}):
            return "API returned an empty response."
        return f"API returned status {payload.get('status_code')} with preview {preview}."
    return None


def format_rows(rows: list[dict[str, Any]], max_rows: int = 5, max_fields: int = 6) -> str:
    formatted_rows = []
    for row in rows[:max_rows]:
        pieces = []
        for key, value in list(row.items())[:max_fields]:
            pieces.append(f"{key}={value}")
        formatted_rows.append("{" + ", ".join(pieces) + "}")
    if len(rows) > max_rows:
        formatted_rows.append(f"... {len(rows) - max_rows} more")
    return "; ".join(formatted_rows)
