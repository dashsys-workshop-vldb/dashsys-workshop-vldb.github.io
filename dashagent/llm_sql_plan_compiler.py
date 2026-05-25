from __future__ import annotations

import re
from typing import Any

from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets


ALLOWED_OPERATORS = {"equals", "contains", "gte", "lte", "in"}
ALLOWED_AGGREGATIONS = {"none", "count", "count_distinct", "max", "min"}
UNSAFE_VALUE_RE = re.compile(r";|--|/\*|\*/|\b(drop|delete|insert|update|alter|create|copy|install|load|pragma)\b", re.I)


def validate_structured_sql_plan(
    plan: dict[str, Any],
    schema_index: SchemaIndex,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    errors: list[str] = []
    warnings: list[str] = []
    alias_suggestions: dict[str, str] = {}
    if not isinstance(plan, dict) or not plan:
        return {"ok": False, "errors": ["SQL plan must be a non-empty JSON object."], "warnings": [], "alias_suggestions": {}}

    tables = _tables_from_plan(plan)
    if not tables:
        errors.append("SQL plan must include primary_table or tables_needed.")

    aliases = context.get("business_term_aliases") if isinstance(context.get("business_term_aliases"), dict) else {}
    for table in tables:
        if not schema_index.table_exists(table):
            suggestion = aliases.get(str(table).lower())
            if suggestion:
                alias_suggestions[str(table)] = suggestion
                errors.append(f"Unknown table: {table}. Alias suggestion: {suggestion}")
            else:
                errors.append(f"Unknown table: {table}.")

    primary_table = _name_from(plan.get("primary_table"))
    if primary_table and schema_index.table_exists(primary_table) and primary_table in schema_index.bridge_tables:
        errors.append(f"Bridge table cannot be primary answer table: {primary_table}.")

    for table, column, source in _column_refs(plan):
        if table and not schema_index.table_exists(table):
            continue
        candidate_tables = [table] if table else [t for t in tables if schema_index.table_exists(t)]
        if column and not any(_column_exists(schema_index, candidate_table, column) for candidate_table in candidate_tables):
            errors.append(f"Unknown column in {source}: {table + '.' if table else ''}{column}.")

    aggregation = _normalize_aggregation(plan, primary_table)
    agg_type = aggregation["type"]
    if agg_type not in ALLOWED_AGGREGATIONS:
        errors.append(f"Unsupported aggregation type: {agg_type}.")

    filters = _normalize_filters(plan.get("filters") or [], primary_table, tables)
    for item in filters:
        if not isinstance(item, dict):
            errors.append("Filter must be an object.")
            continue
        operator = str(item.get("operator") or "").lower()
        if operator not in ALLOWED_OPERATORS:
            errors.append(f"Unsupported filter operator: {operator}.")
        value = item.get("value")
        values = value if isinstance(value, list) else [value]
        for candidate in values:
            if isinstance(candidate, str) and UNSAFE_VALUE_RE.search(candidate):
                errors.append("Unsafe SQL-like fragment detected in filter value.")

    if len([t for t in tables if schema_index.table_exists(t)]) > 1:
        ok, join_errors = _join_supported(tables, schema_index)
        if not ok:
            errors.extend(join_errors)

    return redact_secrets(
        {
            "ok": not errors,
            "errors": sorted(set(errors)),
            "warnings": warnings,
            "alias_suggestions": alias_suggestions,
            "selected_tables": [table for table in tables if schema_index.table_exists(table)],
        }
    )


def compile_structured_sql_plan(
    plan: dict[str, Any],
    schema_index: SchemaIndex,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validate_structured_sql_plan(plan, schema_index, context)
    if not validation["ok"]:
        return {**validation, "sql": "", "join_path": [], "aggregation": _aggregation_label(plan), "filters": _normalize_filters(plan.get("filters") or [], _name_from(plan.get("primary_table")), _tables_from_plan(plan))}

    tables = validation["selected_tables"]
    primary_table = _name_from(plan.get("primary_table")) or tables[0]
    aggregation = _normalize_aggregation(plan, primary_table)
    select_sql, selected_columns = _select_sql(plan, primary_table, schema_index)
    sql_parts = [f"SELECT {select_sql}", f"FROM {_quote_identifier(primary_table)}"]
    join_path = _compile_joins(primary_table, [t for t in tables if t != primary_table], schema_index)
    if not join_path["ok"]:
        return {
            "ok": False,
            "sql": "",
            "errors": join_path["errors"],
            "warnings": [],
            "selected_tables": tables,
            "selected_columns": selected_columns,
            "join_path": [],
            "aggregation": _aggregation_label(plan),
            "filters": _normalize_filters(plan.get("filters") or [], primary_table, tables),
        }
    sql_parts.extend(join_path["sql_parts"])
    filters = _normalize_filters(plan.get("filters") or [], primary_table, tables)
    where_sql = _where_sql(filters, schema_index)
    if where_sql:
        sql_parts.append(f"WHERE {where_sql}")
    order_sql = _order_sql(plan.get("order_by") or [], schema_index)
    if order_sql:
        sql_parts.append(f"ORDER BY {order_sql}")
    if str(aggregation.get("type") or "none").lower() == "none":
        limit = _safe_limit(plan.get("limit"))
        if limit:
            sql_parts.append(f"LIMIT {limit}")
    sql = " ".join(sql_parts)
    return redact_secrets(
        {
            "ok": True,
            "sql": sql,
            "errors": [],
            "warnings": validation.get("warnings", []),
            "selected_tables": tables,
            "selected_columns": selected_columns,
            "join_path": join_path["join_path"],
            "aggregation": _aggregation_label(plan),
            "filters": filters,
        }
    )


def _tables_from_plan(plan: dict[str, Any]) -> list[str]:
    tables: list[str] = []
    primary = _name_from(plan.get("primary_table"))
    if primary:
        tables.append(primary)
    for table in plan.get("tables_needed") or []:
        text = _name_from(table)
        if text:
            tables.append(text)
    for item in plan.get("filters") or []:
        if isinstance(item, dict) and item.get("table"):
            tables.append(_name_from(item["table"]))
    aggregation = _normalize_aggregation(plan, primary)
    if aggregation.get("table"):
        tables.append(_name_from(aggregation["table"]))
    for item in plan.get("order_by") or []:
        if isinstance(item, dict) and item.get("table"):
            tables.append(_name_from(item["table"]))
    return list(dict.fromkeys(tables))


def _column_refs(plan: dict[str, Any]) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    primary_table = _name_from(plan.get("primary_table"))
    aggregation = _normalize_aggregation(plan, primary_table)
    agg_type = aggregation["type"]
    for column in plan.get("columns_needed") or []:
        text = _name_from(column)
        if agg_type in {"count", "count_distinct"} and text.upper() in {"COUNT(*)", "COUNT", "*"}:
            continue
        if text:
            refs.append((primary_table, text, "columns_needed"))
    for item in _normalize_filters(plan.get("filters") or [], primary_table, _tables_from_plan(plan)):
        if isinstance(item, dict) and item.get("column"):
            refs.append((_name_from(item.get("table") or primary_table), _name_from(item["column"]), "filters"))
    if aggregation.get("column") and str(aggregation.get("type") or "none").lower() != "none":
        column = _name_from(aggregation["column"])
        if column != "*":
            refs.append((_name_from(aggregation.get("table") or primary_table), column, "aggregation"))
    for item in plan.get("order_by") or []:
        if isinstance(item, dict) and item.get("column"):
            refs.append((_name_from(item.get("table") or primary_table), _name_from(item["column"]), "order_by"))
    return refs


def _column_exists(schema_index: SchemaIndex, table: str, column: str) -> bool:
    if column == "*":
        return True
    return schema_index.column_exists(table, column)


def _actual_column(schema_index: SchemaIndex, table: str, column: str) -> str:
    wanted = normalize_name(column)
    for candidate in schema_index.columns_for(table):
        if normalize_name(candidate) == wanted:
            return candidate
    return column


def _select_sql(plan: dict[str, Any], primary_table: str, schema_index: SchemaIndex) -> tuple[str, list[str]]:
    aggregation = _normalize_aggregation(plan, primary_table)
    agg_type = aggregation["type"]
    if agg_type in {"count", "count_distinct", "max", "min"}:
        table = _name_from(aggregation.get("table") or primary_table)
        column = _name_from(aggregation.get("column") or "*")
        actual = "*" if column == "*" else _quote_identifier(_actual_column(schema_index, table, column))
        if agg_type == "count":
            expr = f"COUNT({actual}) AS count"
        elif agg_type == "count_distinct":
            expr = f"COUNT(DISTINCT {actual}) AS count"
        elif agg_type == "max":
            expr = f"MAX({actual}) AS max_value"
        else:
            expr = f"MIN({actual}) AS min_value"
        return expr, [column]
    columns = [_name_from(col) for col in plan.get("columns_needed") or [] if _name_from(col)]
    if not columns:
        columns = schema_index.columns_for(primary_table)[:5]
    actual_columns = [_actual_column(schema_index, primary_table, column) for column in columns]
    return ", ".join(_quote_identifier(column) for column in actual_columns), actual_columns


def _where_sql(filters: list[dict[str, Any]], schema_index: SchemaIndex) -> str:
    clauses = []
    for item in filters:
        if not isinstance(item, dict):
            continue
        table = str(item.get("table") or "")
        column = _actual_column(schema_index, table, str(item.get("column") or ""))
        operator = str(item.get("operator") or "").lower()
        value = item.get("value")
        lhs = f"{_quote_identifier(table)}.{_quote_identifier(column)}"
        if operator == "equals":
            clauses.append(f"{lhs} = {_literal(value)}")
        elif operator == "contains":
            clauses.append(f"CAST({lhs} AS VARCHAR) ILIKE {_literal('%' + str(value) + '%')}")
        elif operator == "gte":
            clauses.append(f"{lhs} >= {_literal(value)}")
        elif operator == "lte":
            clauses.append(f"{lhs} <= {_literal(value)}")
        elif operator == "in":
            values = value if isinstance(value, list) else [value]
            clauses.append(f"{lhs} IN ({', '.join(_literal(v) for v in values)})")
    return " AND ".join(clauses)


def _order_sql(items: list[dict[str, Any]], schema_index: SchemaIndex) -> str:
    clauses = []
    for item in items:
        if not isinstance(item, dict):
            continue
        table = str(item.get("table") or "")
        column = _actual_column(schema_index, table, str(item.get("column") or ""))
        direction = str(item.get("direction") or "asc").lower()
        direction = "DESC" if direction == "desc" else "ASC"
        clauses.append(f"{_quote_identifier(table)}.{_quote_identifier(column)} {direction}")
    return ", ".join(clauses)


def _join_supported(tables: list[str], schema_index: SchemaIndex) -> tuple[bool, list[str]]:
    existing = [table for table in tables if schema_index.table_exists(table)]
    if len(existing) <= 1:
        return True, []
    current = {existing[0]}
    remaining = set(existing[1:])
    for hint in schema_index.join_hints:
        if hint.left_table in current and hint.right_table in remaining:
            current.add(hint.right_table)
            remaining.remove(hint.right_table)
        elif hint.right_table in current and hint.left_table in remaining:
            current.add(hint.left_table)
            remaining.remove(hint.left_table)
        if not remaining:
            return True, []
    return False, [f"Unsupported join path for tables: {', '.join(existing)}."]


def _compile_joins(primary_table: str, tables: list[str], schema_index: SchemaIndex) -> dict[str, Any]:
    current = {primary_table}
    remaining = set(tables)
    sql_parts: list[str] = []
    join_path: list[dict[str, str]] = []
    while remaining:
        matched = None
        reverse = False
        for hint in schema_index.join_hints:
            if hint.left_table in current and hint.right_table in remaining:
                matched = hint
                reverse = False
                break
            if hint.right_table in current and hint.left_table in remaining:
                matched = hint
                reverse = True
                break
        if matched is None:
            return {"ok": False, "errors": [f"Unsupported join path for tables: {primary_table}, {', '.join(sorted(remaining))}."], "sql_parts": [], "join_path": join_path}
        if reverse:
            join_table = matched.left_table
            left_table, left_column = matched.right_table, matched.right_column
            right_table, right_column = matched.left_table, matched.left_column
        else:
            join_table = matched.right_table
            left_table, left_column = matched.left_table, matched.left_column
            right_table, right_column = matched.right_table, matched.right_column
        sql_parts.append(
            f"JOIN {_quote_identifier(join_table)} ON {_quote_identifier(left_table)}.{_quote_identifier(left_column)} = {_quote_identifier(right_table)}.{_quote_identifier(right_column)}"
        )
        join_path.append(
            {"left_table": left_table, "left_column": left_column, "right_table": right_table, "right_column": right_column}
        )
        current.add(join_table)
        remaining.remove(join_table)
    return {"ok": True, "errors": [], "sql_parts": sql_parts, "join_path": join_path}


def _safe_limit(value: Any) -> int:
    try:
        limit = int(value)
    except Exception:
        return 50
    if limit <= 0:
        return 50
    return min(limit, 500)


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _aggregation_label(plan: dict[str, Any]) -> str:
    primary_table = _name_from(plan.get("primary_table"))
    return _normalize_aggregation(plan, primary_table)["type"]


def _name_from(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("table", "table_name", "column", "column_name", "name", "id"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_aggregation(plan: dict[str, Any], primary_table: str) -> dict[str, str]:
    raw = plan.get("aggregation")
    if isinstance(raw, list) and raw:
        first = raw[0] if isinstance(raw[0], dict) else {}
        function = str(first.get("function") or first.get("type") or "").lower()
        columns = first.get("columns") if isinstance(first.get("columns"), list) else []
        column = _name_from(first.get("column") or (columns[0] if columns else ""))
        return {
            "type": _normalize_aggregation_type(function, plan),
            "table": _name_from(first.get("table") or primary_table),
            "column": column or "*",
        }
    if isinstance(raw, dict):
        return {
            "type": _normalize_aggregation_type(str(raw.get("type") or raw.get("function") or ""), plan),
            "table": _name_from(raw.get("table") or primary_table),
            "column": _name_from(raw.get("column") or raw.get("column_name") or "*"),
        }
    intent = str(plan.get("answer_intent") or "").upper()
    if intent == "COUNT":
        column = next((_name_from(col) for col in plan.get("columns_needed") or [] if _name_from(col) and _name_from(col).upper() not in {"COUNT(*)", "COUNT"}), "*")
        agg_type = "count_distinct" if column != "*" and _looks_like_id_column(column) else "count"
        return {"type": agg_type, "table": primary_table, "column": column}
    return {"type": "none", "table": primary_table, "column": "*"}


def _normalize_aggregation_type(value: str, plan: dict[str, Any]) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if normalized in {"", "null", "none"}:
        return "count" if str(plan.get("answer_intent") or "").upper() == "COUNT" else "none"
    if normalized in {"distinct_count", "countdistinct", "count_distinct"}:
        return "count_distinct"
    return normalized


def _normalize_filters(filters: list[Any], primary_table: str, tables: list[str]) -> list[dict[str, Any]]:
    default_table = primary_table or (tables[0] if len(tables) == 1 else "")
    normalized: list[dict[str, Any]] = []
    for item in filters:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        column = _name_from(item.get("column") or item.get("column_name"))
        operator = str(item.get("operator") or "").strip().lower()
        if not operator and "value" in item and column:
            operator = "equals"
        normalized.append(
            {
                **item,
                "table": _name_from(item.get("table") or item.get("table_name") or default_table),
                "column": column,
                "operator": operator,
            }
        )
    return normalized


def _looks_like_id_column(column: str) -> bool:
    normalized = normalize_name(column)
    return normalized == "id" or normalized.endswith("_id") or normalized.endswith("id")
