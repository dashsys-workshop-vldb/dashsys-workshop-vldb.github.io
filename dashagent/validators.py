from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .core_tool_policy import clone_validation_result, normalize_sql_for_validation_cache
from .db import is_read_only_sql, strip_sql_comments
from .endpoint_catalog import EndpointCatalog
from .schema_index import SchemaIndex, normalize_name
from .sql_ast_tools import sql_ast_summary


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SQLValidator:
    def __init__(self, schema_index: SchemaIndex, *, enable_ast_validation: bool = True) -> None:
        self.schema_index = schema_index
        self.enable_ast_validation = enable_ast_validation
        self._ast_cache: dict[str, dict[str, Any]] = {}
        self._validation_cache: dict[str, ValidationResult] = {}
        self._validation_cache_hits = 0
        self._validation_cache_misses = 0

    def validate(self, sql: str) -> ValidationResult:
        cache_key = normalize_sql_for_validation_cache(sql)
        if cache_key in self._validation_cache:
            self._validation_cache_hits += 1
            return clone_validation_result(self._validation_cache[cache_key])
        self._validation_cache_misses += 1
        errors: list[str] = []
        warnings: list[str] = []
        ok, error = is_read_only_sql(sql)
        if not ok and error:
            errors.append(error)
            result = ValidationResult(False, errors, warnings)
            self._validation_cache[cache_key] = clone_validation_result(result)
            return result

        cleaned = strip_sql_comments(sql).strip().rstrip(";")
        tables, aliases = extract_tables_and_aliases(cleaned)
        if not tables:
            warnings.append("No table references found.")
        ast = self.ast_summary(sql) if self.enable_ast_validation else {"enabled": False}
        table_suggestions = ast.get("closest_table_suggestions", {}) if isinstance(ast, dict) else {}
        for table in tables:
            if not self.schema_index.table_exists(table):
                suggestions = table_suggestions.get(table, [])
                suffix = f" Suggestions: {', '.join(suggestions)}" if suggestions else ""
                errors.append(f"Unknown table: {table}.{suffix}")

        if self.enable_ast_validation:
            if ast.get("destructive_sql_detected"):
                errors.append("SQL AST detected a blocked write or environment-changing command.")
            if ast.get("parse_error"):
                warnings.append(f"SQLGlot parse warning: {ast.get('parse_error')}")

        if errors:
            result = ValidationResult(False, errors, warnings)
            self._validation_cache[cache_key] = clone_validation_result(result)
            return result

        for alias, column in extract_qualified_columns(cleaned):
            table = aliases.get(alias, alias)
            if table in self.schema_index.tables and not self.schema_index.column_exists(table, column):
                errors.append(self._unknown_column_error(f"{alias}.{column}", ast))

        for column in extract_unqualified_columns(cleaned):
            if column.upper() in SQL_KEYWORDS or column.isdigit():
                continue
            if normalize_name(column) in {"count", "sum", "avg", "min", "max"}:
                continue
            matching_tables = [
                table for table in tables if self.schema_index.column_exists(table, column)
            ]
            if not matching_tables:
                errors.append(self._unknown_column_error(column, ast))

        result = ValidationResult(not errors, sorted(set(errors)), warnings)
        self._validation_cache[cache_key] = clone_validation_result(result)
        return result

    def validation_cache_stats(self) -> dict[str, int]:
        return {
            "entries": len(self._validation_cache),
            "hits": self._validation_cache_hits,
            "misses": self._validation_cache_misses,
            "unsafe_cached_as_safe": sum(
                1
                for sql, result in self._validation_cache.items()
                if result.ok and not is_read_only_sql(sql)[0]
            ),
        }

    def ast_summary(self, sql: str) -> dict[str, Any]:
        if not self.enable_ast_validation:
            return {"enabled": False}
        if sql not in self._ast_cache:
            self._ast_cache[sql] = {"enabled": True, **sql_ast_summary(sql, self.schema_index)}
        return self._ast_cache[sql]

    def _unknown_column_error(self, column: str, ast: dict[str, Any]) -> str:
        suggestions = ast.get("closest_column_suggestions", {}).get(column, []) if isinstance(ast, dict) else []
        if not suggestions and "." in column and isinstance(ast, dict):
            suggestions = ast.get("closest_column_suggestions", {}).get(column.split(".")[-1], [])
        suffix = f" Suggestions: {', '.join(suggestions)}" if suggestions else ""
        return f"Unknown column: {column}.{suffix}"


class APIValidator:
    def __init__(self, endpoint_catalog: EndpointCatalog, allow_unknown: bool = False) -> None:
        self.endpoint_catalog = endpoint_catalog
        self.allow_unknown = allow_unknown

    def validate(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        method = method.upper()
        endpoint = self.endpoint_catalog.match(method, url)
        if endpoint is None and not self.allow_unknown:
            errors.append(f"Unknown or disallowed endpoint: {method} {url}")
        if "{" in url or "}" in url:
            errors.append("Endpoint path contains unresolved path parameters.")
        if params is not None:
            try:
                json.dumps(params)
            except TypeError:
                errors.append("API params are not JSON-serializable.")
        if headers:
            for key in headers:
                if key.lower() in {"authorization", "x-api-key"}:
                    warnings.append(f"Header {key} will be redacted in logs.")
        return ValidationResult(not errors, errors, warnings)


SQL_KEYWORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "ON",
    "AS",
    "AND",
    "OR",
    "NOT",
    "NULL",
    "IS",
    "LIKE",
    "ILIKE",
    "LOWER",
    "UPPER",
    "CAST",
    "VARCHAR",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "GROUP",
    "BY",
    "ORDER",
    "LIMIT",
    "DESC",
    "ASC",
    "DISTINCT",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "IN",
    "BETWEEN",
    "TRUE",
    "FALSE",
}


def unquote_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier[1:-1].replace('""', '"')
    return identifier


def extract_tables_and_aliases(sql: str) -> tuple[list[str], dict[str, str]]:
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+("  # table
        r'"[^"]+"|[a-zA-Z_][\w$]*'
        r")"
        r"(?:\s+(?:AS\s+)?([a-zA-Z_][\w$]*))?",
        re.IGNORECASE,
    )
    tables: list[str] = []
    aliases: dict[str, str] = {}
    for match in pattern.finditer(sql):
        table = unquote_identifier(match.group(1))
        alias = match.group(2)
        if alias and alias.upper() in SQL_KEYWORDS:
            alias = None
        tables.append(table)
        aliases[table] = table
        if alias:
            aliases[alias] = table
    return list(dict.fromkeys(tables)), aliases


def extract_qualified_columns(sql: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r'(?<![A-Za-z0-9_"])(?:"([^"]+)"|([a-zA-Z_][\w$]*))\s*\.\s*(?:"([^"]+)"|([a-zA-Z_][\w$]*))'
    )
    columns = []
    for match in pattern.finditer(sql):
        alias = match.group(1) or match.group(2)
        column = match.group(3) or match.group(4)
        columns.append((alias, column))
    return columns


def extract_unqualified_columns(sql: str) -> list[str]:
    select_match = re.search(r"\bSELECT\b(.*?)\bFROM\b", sql, flags=re.IGNORECASE | re.DOTALL)
    where_match = re.search(
        r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text_parts = []
    if select_match:
        text_parts.append(select_match.group(1))
    if where_match:
        text_parts.append(where_match.group(1))
    text = " ".join(text_parts)
    text = re.sub(r"'(?:''|[^'])*'", " ", text)
    text = re.sub(r'"[^"]+"\s*\.', " ", text)
    text = re.sub(r"[a-zA-Z_][\w$]*\s*\.", " ", text)
    text = re.sub(r"\b[A-Za-z_][\w$]*\s*\([^)]*\)", " ", text)
    text = re.sub(r"\bAS\s+[a-zA-Z_][\w$]*", " ", text, flags=re.IGNORECASE)
    candidates = re.findall(r'"([^"]+)"|(?<![.\w])([a-zA-Z_][\w$]*)(?!\s*\()', text)
    columns = [quoted or bare for quoted, bare in candidates]
    return [column for column in columns if column.upper() not in SQL_KEYWORDS]
