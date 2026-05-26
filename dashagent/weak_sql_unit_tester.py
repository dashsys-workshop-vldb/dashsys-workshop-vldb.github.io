from __future__ import annotations

from typing import Any

from .nlp_generalization_layer import domain_to_table, normalize_prompt_semantics
from .schema_index import normalize_name
from .trajectory import redact_secrets


CRITICAL_TESTS = {
    "intent_test",
    "table_test",
    "column_role_test",
    "filter_test",
    "join_test",
    "aggregation_test",
    "timestamp_test",
    "overbroad_test",
    "group_by_test",
}


def run_sql_semantic_unit_tests(
    prompt: str,
    slots: dict[str, Any] | None,
    sql_plan: dict[str, Any],
    compiled_sql: str,
    schema_context: dict[str, Any] | None,
) -> dict[str, Any]:
    slots = slots if isinstance(slots, dict) else {}
    schema_context = schema_context if isinstance(schema_context, dict) else {}
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else normalize_prompt_semantics(prompt)
    intent = str(slots.get("intent") or sql_plan.get("answer_intent") or nlp.get("canonical_intent") or "UNKNOWN").upper()
    domain = str(slots.get("domain") or nlp.get("canonical_domain") or "UNKNOWN").upper()
    primary_table = str(sql_plan.get("primary_table") or "")
    columns = [str(column) for column in sql_plan.get("columns_needed") or []]
    filters = [item for item in sql_plan.get("filters") or [] if isinstance(item, dict)]
    aggregation = sql_plan.get("aggregation") if isinstance(sql_plan.get("aggregation"), dict) else {}
    failed: list[str] = []
    hints: list[str] = []

    if not _intent_ok(intent, columns, aggregation) and not _acceptable_field_bridge(domain, primary_table, prompt):
        failed.append("intent_test")
        hints.append(f"Use SQL shape that matches intent {intent}.")

    expected_table = domain_to_table(domain)
    retrieved_tables = schema_context.get("retrieved_tables") if isinstance(schema_context.get("retrieved_tables"), list) else []
    if expected_table and primary_table != expected_table and not _acceptable_field_bridge(domain, primary_table, prompt):
        failed.append("table_test")
        hints.append(f"Use primary_table {expected_table} for domain {domain}.")
    elif retrieved_tables and primary_table not in retrieved_tables and not _acceptable_field_bridge(domain, primary_table, prompt):
        failed.append("table_test")
        hints.append(f"Use one of retrieved tables: {', '.join(str(t) for t in retrieved_tables[:3])}.")

    if not _column_roles_ok(intent, primary_table, columns, schema_context) and not _acceptable_field_bridge(domain, primary_table, prompt):
        failed.append("column_role_test")
        hints.append("Select columns with roles requested by the prompt: id/name/status/timestamp as applicable.")

    quoted = list(nlp.get("quoted_entities") or [])
    broad_list = intent == "LIST" and not quoted and not slots.get("entity_terms")
    if quoted and not broad_list and not _has_name_filter(filters, quoted):
        failed.append("filter_test")
        hints.append("Add a name/title/display filter for quoted entity values.")

    status_terms = [term for term in nlp.get("status_terms") or [] if not (intent == "DATE" and term in {"published"})]
    if status_terms and not _has_status_filter(filters, status_terms):
        failed.append("filter_test")
        hints.append("Add a status/state filter for status terms.")

    if intent == "RELATIONSHIP" and not _join_ok(sql_plan, schema_context, compiled_sql):
        failed.append("join_test")
        hints.append("Use only retrieved join candidates for relationship prompts.")

    if intent == "COUNT" and str(aggregation.get("type") or "none").lower() not in {"count", "count_distinct"}:
        failed.append("aggregation_test")
        hints.append("Use count or count_distinct aggregation for count prompts.")

    timestamp_kind = str(nlp.get("timestamp_semantics") or "")
    if intent == "DATE" and timestamp_kind and not _timestamp_ok(primary_table, columns, timestamp_kind, schema_context):
        failed.append("timestamp_test")
        hints.append(f"Use {timestamp_kind} timestamp candidate for date prompts.")

    if quoted and not filters:
        failed.append("overbroad_test")
        hints.append("Entity-specific prompts need a filter to avoid broad SQL.")
    if _needs_group_by(prompt, intent) and not _has_group_by(sql_plan, compiled_sql):
        failed.append("group_by_test")
        hints.append("Add GROUP BY for grouped count prompts.")
    if not _answer_shape_ok(intent, columns, aggregation):
        failed.append("answer_shape_test")
        hints.append("Select columns or aggregation that can render the requested answer shape.")

    unique_failed = sorted(set(failed))
    critical_failures = sorted(test for test in unique_failed if test in CRITICAL_TESTS)
    semantic_score = round(max(0.0, 1.0 - 0.14 * len(unique_failed)), 4)
    return redact_secrets(
        {
            "passed": not critical_failures,
            "failed_tests": unique_failed,
            "critical_failures": critical_failures,
            "repair_hints": list(dict.fromkeys(hints)),
            "semantic_score": semantic_score,
        }
    )


def _intent_ok(intent: str, columns: list[str], aggregation: dict[str, Any]) -> bool:
    agg_type = str(aggregation.get("type") or "none").lower()
    if intent == "COUNT":
        return agg_type in {"count", "count_distinct"}
    if intent == "DATE":
        return any(_is_timestamp(column) for column in columns)
    if intent == "STATUS":
        return any(_is_status(column) for column in columns)
    if intent == "LIST":
        return any(_is_id(column) or _is_name(column) for column in columns)
    return True


def _column_roles_ok(intent: str, table: str, columns: list[str], context: dict[str, Any]) -> bool:
    roles = ((context.get("column_roles") or {}).get(table) or {}) if isinstance(context.get("column_roles"), dict) else {}
    selected = {normalize_name(column) for column in columns}
    if intent == "COUNT":
        return True
    if intent == "DATE":
        return bool(selected & {normalize_name(column) for column in roles.get("timestamp", [])})
    if intent == "STATUS":
        return bool(selected & {normalize_name(column) for column in roles.get("status", [])})
    if intent == "LIST":
        required = set()
        required.update(normalize_name(column) for column in roles.get("id", [])[:1])
        required.update(normalize_name(column) for column in roles.get("name", [])[:1])
        return bool(selected & required)
    return True


def _has_name_filter(filters: list[dict[str, Any]], quoted: list[str]) -> bool:
    quoted_norm = {str(value).lower() for value in quoted}
    for item in filters:
        column = normalize_name(str(item.get("column") or ""))
        value = str(item.get("value") or "").lower()
        if any(marker in column for marker in ("name", "title", "display")) and value in quoted_norm:
            return True
    return False


def _has_status_filter(filters: list[dict[str, Any]], status_terms: list[str]) -> bool:
    wanted = {str(value).lower() for value in status_terms}
    for item in filters:
        column = normalize_name(str(item.get("column") or ""))
        value = str(item.get("value") or "").lower()
        if any(marker in column for marker in ("status", "state", "lifecycle")) and value in wanted:
            return True
    return False


def _join_ok(plan: dict[str, Any], context: dict[str, Any], compiled_sql: str) -> bool:
    tables = [str(table) for table in plan.get("tables_needed") or []]
    if len(tables) <= 1:
        return False
    join_candidates = context.get("join_candidates") if isinstance(context.get("join_candidates"), list) else []
    joined_tables = {item.get("left_table") for item in join_candidates} | {item.get("right_table") for item in join_candidates}
    return bool(set(tables) <= joined_tables or " join " in str(compiled_sql).lower())


def _timestamp_ok(table: str, columns: list[str], kind: str, context: dict[str, Any]) -> bool:
    candidates = (((context.get("timestamp_candidates") or {}).get(table) or {}).get(kind) or []) if isinstance(context.get("timestamp_candidates"), dict) else []
    if candidates:
        return bool({normalize_name(column) for column in columns} & {normalize_name(column) for column in candidates})
    if kind == "published":
        return any(any(marker in normalize_name(column) for marker in ("deployed", "published", "launch", "release")) for column in columns)
    if kind == "updated":
        return any(any(marker in normalize_name(column) for marker in ("updated", "modified")) for column in columns)
    if kind == "created":
        return any("created" in normalize_name(column) for column in columns)
    return any(_is_timestamp(column) for column in columns)


def _is_id(column: str) -> bool:
    norm = normalize_name(column)
    return norm == "id" or norm.endswith("id")


def _is_name(column: str) -> bool:
    return any(marker in normalize_name(column) for marker in ("name", "title", "display"))


def _is_status(column: str) -> bool:
    return any(marker in normalize_name(column) for marker in ("status", "state", "lifecycle"))


def _is_timestamp(column: str) -> bool:
    return any(marker in normalize_name(column) for marker in ("time", "date", "created", "updated", "deployed", "published", "modified"))


def _needs_group_by(prompt: str, intent: str) -> bool:
    lowered = prompt.lower()
    return intent == "COUNT" and any(marker in lowered for marker in (" group by ", " by status", " by type", " per ", " for each "))


def _has_group_by(plan: dict[str, Any], compiled_sql: str) -> bool:
    return bool(plan.get("group_by") or " group by " in str(compiled_sql).lower())


def _answer_shape_ok(intent: str, columns: list[str], aggregation: dict[str, Any]) -> bool:
    if intent == "COUNT":
        return str(aggregation.get("type") or "none").lower() in {"count", "count_distinct"}
    if intent in {"LIST", "STATUS", "DATE", "DETAIL", "RELATIONSHIP"}:
        return bool(columns)
    return True


def _acceptable_field_bridge(domain: str, primary_table: str, prompt: str) -> bool:
    if domain != "FIELD":
        return False
    if primary_table != "hkg_br_segment_property":
        return False
    lowered = prompt.lower()
    return "field" in lowered and any(marker in lowered for marker in ("segment", "audience", "person:"))
