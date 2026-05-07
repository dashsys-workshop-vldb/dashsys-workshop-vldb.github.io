from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any

from .answer_reranker import select_best_answer
from .answer_templates import classify_answer_family, render_answer_template


@dataclass
class AnswerResult:
    answer: str
    diagnostics: dict[str, Any]


EVIDENCE_AWARE_DRY_RUN_FLAG = "ENABLE_EVIDENCE_AWARE_DRY_RUN_ANSWERS"


def synthesize_answer(query: str, tool_results: list[dict[str, Any]]) -> str:
    return synthesize_answer_with_diagnostics(query, tool_results).answer


def synthesize_answer_with_diagnostics(query: str, tool_results: list[dict[str, Any]]) -> AnswerResult:
    base_answer = synthesize_base_answer(query, tool_results)
    dry_run_candidate = evidence_aware_dry_run_answer(query, tool_results)
    if dry_run_candidate:
        base_answer = dry_run_candidate
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


def evidence_aware_dry_run_answer(query: str, tool_results: list[dict[str, Any]]) -> str | None:
    """Build a richer dry-run answer without treating dry-run previews as payload evidence."""
    if not _evidence_aware_dry_run_enabled():
        return None
    api_results = [result for result in tool_results if result.get("type") == "api"]
    if not any(result.get("payload", {}).get("dry_run") for result in api_results):
        return None

    sql_results = [result for result in tool_results if result.get("type") == "sql"]
    pieces: list[str] = []
    sql_answer = summarize_sql(sql_results)
    if sql_answer:
        pieces.append(sql_answer)

    query_values = _query_visible_values(query)
    request_facts = _selected_request_facts(query, sql_results, api_results)
    if query_values:
        pieces.append(f"Query-visible value(s): {', '.join(query_values[:5])}.")
    if request_facts:
        pieces.append(f"Selected dry-run request evidence: {', '.join(request_facts[:5])}.")

    family = classify_answer_family(query)
    requested = _requested_payload_description(query, family)
    pieces.append(
        f"The requested {requested} is unavailable in dry-run mode because no live API payload was returned."
    )
    pieces.append("Live API verification was not executed because Adobe credentials are unavailable.")
    return " ".join(pieces)


def _evidence_aware_dry_run_enabled() -> bool:
    return os.getenv(EVIDENCE_AWARE_DRY_RUN_FLAG, "0").strip().lower() in {"1", "true", "yes", "on"}


def _query_visible_values(query: str) -> list[str]:
    values: list[str] = []
    values.extend(value.strip() for pair in re.findall(r"'([^']+)'|\"([^\"]+)\"", query) for value in pair if value.strip())
    values.extend(re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", query, flags=re.I))
    values.extend(re.findall(r"\b01[A-Z0-9]{20,}\b", query))
    values.extend(re.findall(r"\b[a-f0-9]{20,}\b", query, flags=re.I))
    values.extend(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query))
    lowered = query.lower()
    for status in ["failed", "failure", "success", "succeeded", "queued", "active", "inactive", "published", "draft"]:
        if re.search(rf"\b{re.escape(status)}\b", lowered):
            values.append(status)
    return _dedupe_preserve(values)


def _selected_request_facts(
    query: str,
    sql_results: list[dict[str, Any]],
    api_results: list[dict[str, Any]],
) -> list[str]:
    supported_text = " ".join(_query_visible_values(query) + _sql_scalar_values(sql_results)).lower()
    facts: list[str] = []
    for result in api_results:
        payload = result.get("payload", {})
        if not payload.get("dry_run"):
            continue
        step = result.get("step", {})
        family = str(step.get("family") or "").replace("_", " ").strip()
        if family:
            facts.append(f"endpoint family {family}")
        params = step.get("params")
        if not isinstance(params, dict):
            params = payload.get("params")
        if isinstance(params, dict):
            for key, value in sorted(params.items()):
                if _safe_request_param(key, value, supported_text):
                    facts.append(f"{key}={value}")
    return _dedupe_preserve(facts)


def _safe_request_param(key: Any, value: Any, supported_text: str) -> bool:
    key_text = str(key)
    if re.search(r"secret|token|authorization|password|credential|api[-_]?key", key_text, flags=re.I):
        return False
    if isinstance(value, (dict, list)) or value in (None, ""):
        return False
    value_text = str(value)
    if value_text.lower() in supported_text:
        return True
    if not re.search(r"\d", value_text) and len(value_text) <= 32:
        return True
    return False


def _sql_scalar_values(sql_results: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for result in sql_results:
        payload = result.get("payload", {})
        if not payload.get("ok"):
            continue
        for row in payload.get("rows") or []:
            if not isinstance(row, dict):
                continue
            for value in row.values():
                if value not in (None, "", [], {}):
                    values.append(str(value))
    return values


def _requested_payload_description(query: str, family: str) -> str:
    lowered = query.lower()
    if "file" in lowered:
        return "file list or file details"
    if any(token in lowered for token in ["how many", "count", "number of", "total"]):
        return f"{_family_noun(family)} count"
    if "status" in lowered or "state" in lowered:
        return f"{_family_noun(family)} status"
    if any(token in lowered for token in ["when", "date", "time", "recent", "latest"]):
        return f"{_family_noun(family)} date or timestamp"
    if "list" in lowered or "all " in lowered:
        return f"{_family_noun(family)} list"
    return f"{_family_noun(family)} details"


def _family_noun(family: str) -> str:
    return {
        "observability_metrics": "observability metric",
        "segment_definitions": "segment definition",
        "segment_jobs": "segment evaluation job",
        "tags": "tag",
        "batch": "batch",
        "merge_policy": "merge policy",
        "schema_dataset": "schema or dataset",
        "audit_destination_mapping": "audit event",
        "segment_destination": "segment-destination relationship",
    }.get(family, family.replace("_", " "))


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


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
