from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, process
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from .db import strip_sql_comments
from .schema_index import SchemaIndex, normalize_name


DESTRUCTIVE_EXPRESSIONS = (
    exp.Alter,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Update,
)

DESTRUCTIVE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|ATTACH|DETACH|MERGE|TRUNCATE|VACUUM|INSTALL|LOAD|SET)\b",
    re.IGNORECASE,
)


def parse_sql_ast(sql: str, dialect: str = "duckdb") -> exp.Expression:
    return parse_one(strip_sql_comments(sql).strip().rstrip(";"), read=dialect)


def extract_sql_tables(sql: str) -> list[str]:
    try:
        tree = parse_sql_ast(sql)
    except ParseError:
        return []
    return _dedupe(_table_name(table) for table in tree.find_all(exp.Table) if _table_name(table))


def extract_sql_columns(sql: str) -> list[str]:
    try:
        tree = parse_sql_ast(sql)
    except ParseError:
        return []
    columns = []
    for column in tree.find_all(exp.Column):
        if column.name == "*":
            continue
        if column.table:
            columns.append(f"{column.table}.{column.name}")
        else:
            columns.append(column.name)
    return _dedupe(columns)


def normalize_sql_ast(sql: str) -> str:
    return parse_sql_ast(sql).sql(dialect="duckdb", pretty=False)


def detect_destructive_sql(sql: str) -> bool:
    cleaned = strip_sql_comments(sql)
    if DESTRUCTIVE_WORDS.search(cleaned):
        return True
    try:
        tree = parse_sql_ast(cleaned)
    except ParseError:
        return False
    return any(isinstance(node, DESTRUCTIVE_EXPRESSIONS) for node in tree.walk())


def detect_unknown_tables(sql: str, allowed_tables: set[str]) -> list[str]:
    allowed = {normalize_name(table): table for table in allowed_tables}
    unknown = []
    for table in extract_sql_tables(sql):
        if normalize_name(table) not in allowed:
            unknown.append(table)
    return _dedupe(unknown)


def detect_unknown_columns(sql: str, schema_index: SchemaIndex) -> list[str]:
    try:
        tree = parse_sql_ast(sql)
    except ParseError:
        return []
    tables = extract_sql_tables(sql)
    alias_map = _alias_map(tree)
    unknown: list[str] = []
    for column in tree.find_all(exp.Column):
        if column.name == "*":
            continue
        if _is_pseudo_column(column.name):
            continue
        qualifier = column.table
        if qualifier:
            table = alias_map.get(qualifier, qualifier)
            if table in schema_index.tables and not schema_index.column_exists(table, column.name):
                unknown.append(f"{qualifier}.{column.name}")
            elif table not in schema_index.tables and normalize_name(table) not in {normalize_name(item) for item in tables}:
                unknown.append(f"{qualifier}.{column.name}")
            continue
        if tables and not any(schema_index.column_exists(table, column.name) for table in tables if table in schema_index.tables):
            unknown.append(column.name)
    return _dedupe(unknown)


def suggest_closest_tables(unknown_tables: list[str], allowed_tables: set[str]) -> dict[str, list[str]]:
    choices = sorted(allowed_tables)
    suggestions: dict[str, list[str]] = {}
    for table in unknown_tables:
        semantic = _semantic_table_suggestions(table, allowed_tables)
        fuzzy = [match[0] for match in process.extract(table, choices, scorer=fuzz.WRatio, limit=4) if match[1] >= 45]
        suggestions[table] = _dedupe([*semantic, *fuzzy])[:4]
    return suggestions


def suggest_closest_columns(unknown_columns: list[str], schema_index: SchemaIndex) -> dict[str, list[str]]:
    all_columns = sorted({column for table in schema_index.tables for column in schema_index.columns_for(table)})
    suggestions: dict[str, list[str]] = {}
    for column in unknown_columns:
        bare = column.split(".")[-1]
        suggestions[column] = [
            match[0]
            for match in process.extract(bare, all_columns, scorer=fuzz.WRatio, limit=4)
            if match[1] >= 45
        ]
    return suggestions


def sql_ast_summary(sql: str, schema_index: SchemaIndex, dialect: str = "duckdb") -> dict[str, Any]:
    summary: dict[str, Any] = {
        "parsed_ok": False,
        "selected_tables": [],
        "selected_columns": [],
        "unknown_tables": [],
        "unknown_columns": [],
        "destructive_sql_detected": detect_destructive_sql(sql),
        "closest_table_suggestions": {},
        "closest_column_suggestions": {},
    }
    try:
        tree = parse_sql_ast(sql, dialect=dialect)
        summary["parsed_ok"] = True
        summary["normalized_sql"] = tree.sql(dialect=dialect, pretty=False)
    except ParseError as exc:
        summary["parse_error"] = str(exc).splitlines()[0][:300]
        return summary
    allowed_tables = set(schema_index.tables)
    unknown_tables = detect_unknown_tables(sql, allowed_tables)
    unknown_columns = detect_unknown_columns(sql, schema_index)
    summary.update(
        {
            "selected_tables": extract_sql_tables(sql),
            "selected_columns": extract_sql_columns(sql),
            "unknown_tables": unknown_tables,
            "unknown_columns": unknown_columns,
            "closest_table_suggestions": suggest_closest_tables(unknown_tables, allowed_tables),
            "closest_column_suggestions": suggest_closest_columns(unknown_columns, schema_index),
        }
    )
    return summary


def _alias_map(tree: exp.Expression) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        name = _table_name(table)
        if not name:
            continue
        aliases[name] = name
        alias = table.alias
        if alias:
            aliases[alias] = name
    return aliases


def _table_name(table: exp.Table) -> str:
    return str(table.name or "").strip('"`')


def _is_pseudo_column(column: str) -> bool:
    return normalize_name(column) in {"rownum"}


def _semantic_table_suggestions(name: str, allowed_tables: set[str]) -> list[str]:
    normalized = normalize_name(name)
    aliases = {
        "journey": ["dim_campaign"],
        "journeys": ["dim_campaign"],
        "campaign": ["dim_campaign"],
        "audience": ["dim_segment"],
        "audiences": ["dim_segment"],
        "segment": ["dim_segment"],
        "segments": ["dim_segment"],
        "destination": ["dim_target"],
        "destinations": ["dim_target"],
        "target": ["dim_target"],
        "schema": ["dim_blueprint"],
        "schemas": ["dim_blueprint"],
    }
    return [table for table in aliases.get(normalized, []) if table in allowed_tables]


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result
