from __future__ import annotations

import re
from typing import Any

from .llm_sql_context_builder import infer_answer_intent
from .schema_index import normalize_name
from .trajectory import redact_secrets


ENTITY_TABLE_HINTS = (
    (("journey", "journeys", "campaign", "campaigns"), "dim_campaign"),
    (("audience", "audiences", "segment", "segments"), "dim_segment"),
    (("dataset", "datasets", "collection", "collections"), "dim_collection"),
    (("schema", "schemas", "blueprint", "blueprints"), "dim_blueprint"),
    (("destination", "destinations", "target", "targets"), "dim_target"),
    (("connector", "connectors", "source", "sources", "dataflow", "dataflows"), "dim_connector"),
)

STATUS_TERMS = {"active", "inactive", "failed", "succeeded", "success", "draft", "published", "deployed", "unpublished"}


def verify_sql_plan_semantics(
    prompt: str,
    evidence_source_plan: dict[str, Any] | None,
    structured_sql_plan: dict[str, Any],
    schema_context: dict[str, Any],
    answer_intent: str | None = None,
) -> dict[str, Any]:
    """Check a structured SQL plan against prompt semantics before execution.

    This is intentionally conservative and diagnostic-only for the Pure LLM
    shadow agent. It does not use query IDs or gold answers.
    """

    plan = structured_sql_plan if isinstance(structured_sql_plan, dict) else {}
    prompt_l = prompt.lower()
    intent = _intent(prompt, answer_intent or plan.get("answer_intent"))
    table = _name(plan.get("primary_table")) or _first(_tables(plan))
    columns = [_name(item) for item in plan.get("columns_needed") or [] if _name(item)]
    filters = _filters(plan)
    aggregation = _aggregation(plan)
    errors: list[str] = []
    warnings: list[str] = []

    expected_table = _expected_table(prompt_l, schema_context)
    if expected_table and table and table != expected_table:
        errors.append(f"Entity/table mismatch: prompt indicates {expected_table}, but plan selected {table}.")
    if table and _business_term_table(table):
        errors.append(f"Plan uses business term as table instead of actual schema table: {table}.")

    if intent == "COUNT" and aggregation not in {"count", "count_distinct"}:
        errors.append("COUNT prompt must use count or count_distinct aggregation.")
    if intent == "LIST" and not _has_id_or_name(columns):
        errors.append("LIST prompt should select an ID or name column when available.")
    if intent == "STATUS" and not (_has_status_column(columns) or _has_status_filter(filters)):
        errors.append("STATUS prompt must include a status/state column or status/state filter.")
    if intent == "DATE":
        if not _has_date_column(columns):
            errors.append("DATE/WHEN prompt must include a timestamp/date-like column.")
        if _mentions_published(prompt_l) and not _has_published_timestamp(columns):
            errors.append("Published/deployed DATE prompt should select a published timestamp such as LASTDEPLOYEDTIME.")

    quoted_values = _quoted_values(prompt)
    if quoted_values and not _broad_list(prompt_l):
        if not any(_filter_matches_quoted_entity(item, quoted_values) for item in filters):
            errors.append("Quoted/named entity prompt requires a name/title/display filter.")

    if any(_null_filter(item) for item in filters):
        warnings.append("NULL filter detected; this often over-constrains broad list prompts.")
        if not _asks_for_null(prompt_l):
            errors.append("Unexpected NULL filter for prompt without null/missing intent.")

    if _status_terms(prompt_l) and not _has_status_filter(filters) and intent in {"STATUS", "LIST"}:
        warnings.append("Status term present without status/state filter.")

    checks = 5
    semantic_score = max(0.0, round(1.0 - (len(errors) / checks), 4))
    return redact_secrets(
        {
            "ok": not errors,
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
            "repair_hint": _repair_hint(errors, warnings, expected_table),
            "semantic_score": 1.0 if not errors else semantic_score,
            "expected_table": expected_table,
            "selected_table": table,
            "selected_columns": columns,
            "selected_aggregation": aggregation,
            "selected_filters": filters,
            "evidence_source_plan": evidence_source_plan or {},
        }
    )


def _intent(prompt: str, value: Any) -> str:
    text = str(value or "").upper()
    if text in {"COUNT", "LIST", "STATUS", "DATE", "DETAIL", "YES_NO"}:
        return text
    return infer_answer_intent(prompt)


def _expected_table(prompt_l: str, schema_context: dict[str, Any]) -> str | None:
    available = {str(item.get("table")) for item in schema_context.get("top_tables", []) if isinstance(item, dict)}
    aliases = schema_context.get("business_term_aliases") if isinstance(schema_context.get("business_term_aliases"), dict) else {}
    for terms, table in ENTITY_TABLE_HINTS:
        if any(re.search(rf"\b{re.escape(term)}\b", prompt_l) for term in terms):
            candidate = aliases.get(terms[0]) or table
            if not available or candidate in available:
                return candidate
            return table
    return None


def _tables(plan: dict[str, Any]) -> list[str]:
    tables = []
    if _name(plan.get("primary_table")):
        tables.append(_name(plan.get("primary_table")))
    for table in plan.get("tables_needed") or []:
        text = _name(table)
        if text:
            tables.append(text)
    return list(dict.fromkeys(tables))


def _filters(plan: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in plan.get("filters") or []:
        if isinstance(item, dict):
            result.append(item)
    return result


def _aggregation(plan: dict[str, Any]) -> str:
    raw = plan.get("aggregation")
    if isinstance(raw, dict):
        return str(raw.get("type") or raw.get("function") or "none").lower()
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return str(raw[0].get("type") or raw[0].get("function") or "none").lower()
    return "count" if str(plan.get("answer_intent") or "").upper() == "COUNT" else "none"


def _name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("table", "table_name", "column", "column_name", "name", "id"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _first(values: list[str]) -> str:
    return values[0] if values else ""


def _has_id_or_name(columns: list[str]) -> bool:
    return any(_is_id_column(column) or _is_name_column(column) for column in columns)


def _has_status_column(columns: list[str]) -> bool:
    return any(normalize_name(column) in {"status", "state", "lifecyclestatus"} or "status" in normalize_name(column) for column in columns)


def _has_status_filter(filters: list[dict[str, Any]]) -> bool:
    return any(_has_status_column([str(item.get("column") or "")]) for item in filters)


def _has_date_column(columns: list[str]) -> bool:
    return any(any(marker in normalize_name(column) for marker in ("time", "date", "deployed", "published", "created", "updated")) for column in columns)


def _has_published_timestamp(columns: list[str]) -> bool:
    return any(any(marker in normalize_name(column) for marker in ("deployed", "published")) for column in columns)


def _is_id_column(column: str) -> bool:
    normalized = normalize_name(column)
    return normalized == "id" or normalized.endswith("id")


def _is_name_column(column: str) -> bool:
    normalized = normalize_name(column)
    return normalized in {"name", "title", "displayname"} or normalized.endswith("name")


def _quoted_values(prompt: str) -> list[str]:
    return [match.group(1) or match.group(2) for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", prompt)]


def _filter_matches_quoted_entity(item: dict[str, Any], quoted_values: list[str]) -> bool:
    column = normalize_name(str(item.get("column") or ""))
    value = str(item.get("value") or "")
    return any(value == quoted for quoted in quoted_values) and any(marker in column for marker in ("name", "title", "display", "label"))


def _null_filter(item: dict[str, Any]) -> bool:
    return item.get("value") is None or str(item.get("value")).lower() in {"null", "none"}


def _asks_for_null(prompt_l: str) -> bool:
    return any(term in prompt_l for term in ("null", "missing", "empty", "unset", "without"))


def _mentions_published(prompt_l: str) -> bool:
    return any(term in prompt_l for term in ("published", "publish", "deployed", "deployment"))


def _broad_list(prompt_l: str) -> bool:
    return bool(re.search(r"\b(all|every)\b", prompt_l))


def _status_terms(prompt_l: str) -> set[str]:
    return {term for term in STATUS_TERMS if re.search(rf"\b{re.escape(term)}\b", prompt_l)}


def _business_term_table(table: str) -> bool:
    normalized = normalize_name(table)
    return normalized in {"journey", "audience", "dataset", "schema", "destination", "connector", "dataflow"}


def _repair_hint(errors: list[str], warnings: list[str], expected_table: str | None) -> str:
    hints = []
    if expected_table:
        hints.append(f"use primary_table {expected_table}")
    if errors:
        hints.append("fix semantic errors: " + "; ".join(errors[:4]))
    if warnings:
        hints.append("address warnings: " + "; ".join(warnings[:2]))
    return " | ".join(hints) if hints else "semantic plan is compatible"
