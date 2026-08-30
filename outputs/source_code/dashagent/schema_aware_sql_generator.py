from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .db import DuckDBDatabase, quote_ident
from .query_analysis import QueryAnalysis
from .query_tokens import QueryTokens, extract_query_tokens
from .relevance_scorer import score_relevance
from .schema_index import JoinHint, SchemaIndex, normalize_name
from .sql_ast_tools import sql_ast_summary
from .validators import SQLValidator


@dataclass(frozen=True)
class SchemaAwareSQLCandidate:
    candidate_id: str
    sql: str
    reason: str
    selected_tables: list[str]
    selected_columns: list[str]
    join_path: list[dict[str, str]] = field(default_factory=list)
    aggregation: str | None = None
    filters: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in (None, [], {}, "")}


@dataclass(frozen=True)
class SchemaAwareSQLGenerationResult:
    query: str
    candidates: list[SchemaAwareSQLCandidate]
    rejected_candidates: list[SchemaAwareSQLCandidate]
    warnings: list[str] = field(default_factory=list)

    @property
    def selected_candidate(self) -> SchemaAwareSQLCandidate | None:
        return self.candidates[0] if self.candidates else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidate_count": len(self.candidates),
            "rejected_candidate_count": len(self.rejected_candidates),
            "selected_candidate": self.selected_candidate.to_dict() if self.selected_candidate else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "rejected_candidates": [candidate.to_dict() for candidate in self.rejected_candidates],
            "warnings": self.warnings,
        }


def generate_schema_aware_sql_candidates(
    query: str,
    schema_index: SchemaIndex,
    *,
    analysis: QueryAnalysis | None = None,
    selected_tables: list[str] | None = None,
    max_candidates: int = 5,
    db: DuckDBDatabase | None = None,
    execute_probe: bool = False,
) -> SchemaAwareSQLGenerationResult:
    tokens = analysis.tokens if analysis else extract_query_tokens(query)
    top_tables = _top_tables(query, schema_index, analysis=analysis, selected_tables=selected_tables)
    raw: list[SchemaAwareSQLCandidate] = []
    warnings: list[str] = []

    if not top_tables:
        return SchemaAwareSQLGenerationResult(query=query, candidates=[], rejected_candidates=[], warnings=["No schema tables available."])

    primary_table = top_tables[0]
    if _asks_count(tokens):
        raw.append(_count_candidate(query, schema_index, primary_table, tokens))
    raw.append(_single_table_candidate(query, schema_index, primary_table, tokens))

    join_candidate = _relationship_join_candidate(query, schema_index, top_tables, tokens)
    if join_candidate is not None:
        raw.insert(0 if _relationship_requested(tokens) else len(raw), join_candidate)

    validated: list[SchemaAwareSQLCandidate] = []
    rejected: list[SchemaAwareSQLCandidate] = []
    seen_sql: set[str] = set()
    for candidate in raw:
        if candidate.sql in seen_sql:
            continue
        seen_sql.add(candidate.sql)
        checked = candidate_with_validation(candidate, schema_index, db=db, execute_probe=execute_probe)
        if _candidate_is_valid(checked):
            validated.append(checked)
        else:
            rejected.append(checked)

    validated = sorted(validated, key=lambda item: (-item.confidence, item.candidate_id))[:max_candidates]
    if not validated:
        warnings.append("No schema-aware SQL candidate passed validation.")
    return SchemaAwareSQLGenerationResult(query=query, candidates=validated, rejected_candidates=rejected, warnings=warnings)


def candidate_with_validation(
    candidate: SchemaAwareSQLCandidate,
    schema_index: SchemaIndex,
    *,
    db: DuckDBDatabase | None = None,
    execute_probe: bool = False,
) -> SchemaAwareSQLCandidate:
    validation = validate_schema_aware_sql(candidate.sql, schema_index, db=db, execute_probe=execute_probe)
    return SchemaAwareSQLCandidate(
        candidate_id=candidate.candidate_id,
        sql=candidate.sql,
        reason=candidate.reason,
        selected_tables=candidate.selected_tables,
        selected_columns=candidate.selected_columns,
        join_path=candidate.join_path,
        aggregation=candidate.aggregation,
        filters=candidate.filters,
        confidence=candidate.confidence,
        warnings=candidate.warnings,
        validation=validation,
    )


def validate_schema_aware_sql(
    sql: str,
    schema_index: SchemaIndex,
    *,
    db: DuckDBDatabase | None = None,
    execute_probe: bool = False,
) -> dict[str, Any]:
    validator = SQLValidator(schema_index)
    validation = validator.validate(sql)
    ast = sql_ast_summary(sql, schema_index)
    probe: dict[str, Any] | None = None
    if execute_probe and validation.ok and ast.get("parsed_ok") and db is not None:
        probe = db.execute_sql(sql, max_rows=1, allow_full_result=False)
    return {
        "ok": bool(validation.ok)
        and bool(ast.get("parsed_ok"))
        and not ast.get("unknown_tables")
        and not ast.get("unknown_columns")
        and not ast.get("destructive_sql_detected")
        and (probe is None or bool(probe.get("ok"))),
        "validator_ok": validation.ok,
        "validator_errors": validation.errors,
        "validator_warnings": validation.warnings,
        "ast_parsed_ok": bool(ast.get("parsed_ok")),
        "unknown_tables": ast.get("unknown_tables", []),
        "unknown_columns": ast.get("unknown_columns", []),
        "destructive_sql_detected": bool(ast.get("destructive_sql_detected")),
        "selected_tables": ast.get("selected_tables", []),
        "selected_columns": ast.get("selected_columns", []),
        "execution_probe": _compact_probe(probe),
    }


def _top_tables(
    query: str,
    schema_index: SchemaIndex,
    *,
    analysis: QueryAnalysis | None,
    selected_tables: list[str] | None,
) -> list[str]:
    ordered: list[str] = []
    if analysis is not None:
        ordered.extend(item.name for item in analysis.relevance.tables)
        ordered.extend(analysis.lookup_path.tables)
    ordered.extend(selected_tables or [])
    if not ordered:
        relevance = score_relevance(query, schema_index)
        ordered.extend(item.name for item in relevance.tables)
    ordered.extend(_keyword_table_preferences(query, schema_index))
    ordered.extend(schema_index.tables)
    return _dedupe(table for table in ordered if table in schema_index.tables)[:8]


def _keyword_table_preferences(query: str, schema_index: SchemaIndex) -> list[str]:
    lowered = query.lower()
    preferences = {
        "campaign": ["dim_campaign"],
        "journey": ["dim_campaign"],
        "segment": ["dim_segment"],
        "audience": ["dim_segment"],
        "destination": ["dim_target"],
        "target": ["dim_target"],
        "connector": ["dim_connector"],
        "schema": ["dim_blueprint", "dim_collection"],
        "dataset": ["dim_collection"],
        "collection": ["dim_collection"],
        "property": ["dim_property"],
        "field": ["dim_property"],
    }
    tables: list[str] = []
    for token, candidates in preferences.items():
        if token in lowered:
            tables.extend(table for table in candidates if table in schema_index.tables)
    return tables


def _count_candidate(query: str, schema: SchemaIndex, table: str, tokens: QueryTokens) -> SchemaAwareSQLCandidate:
    alias = "T0"
    columns = schema.columns_for(table)
    filters = _filters_for_table(alias, columns, tokens)
    where = f" WHERE {' AND '.join(filters)}" if filters else ""
    aggregation = "COUNT(*)"
    selected_columns: list[str] = []
    if _asks_distinct(tokens):
        count_column = _primary_id_column(schema, table) or _first_id_column(schema, table)
        if count_column:
            aggregation = f"COUNT(DISTINCT {alias}.{quote_ident(count_column)})"
            selected_columns = [count_column]
    sql = f"SELECT {aggregation} AS count FROM {quote_ident(table)} AS {alias}{where}"
    return SchemaAwareSQLCandidate(
        candidate_id="schema_count_distinct" if "DISTINCT" in aggregation else "schema_count",
        sql=sql,
        reason="Schema-aware count candidate from selected table and query filters.",
        selected_tables=[table],
        selected_columns=selected_columns,
        aggregation=aggregation,
        filters=filters,
        confidence=0.82 if "DISTINCT" in aggregation else 0.78,
        warnings=[] if filters else ["No value filter inferred from prompt."],
    )


def _single_table_candidate(query: str, schema: SchemaIndex, table: str, tokens: QueryTokens) -> SchemaAwareSQLCandidate:
    alias = "T0"
    columns = schema.columns_for(table)
    selected = _display_columns(query, columns, tokens)
    filters = _filters_for_table(alias, columns, tokens)
    where = f" WHERE {' AND '.join(filters)}" if filters else ""
    order = _order_clause(alias, columns, tokens)
    select_sql = ", ".join(f"{alias}.{quote_ident(column)}" for column in selected) if selected else "*"
    sql = f"SELECT {select_sql} FROM {quote_ident(table)} AS {alias}{where}{order} LIMIT 50"
    return SchemaAwareSQLCandidate(
        candidate_id="schema_single_table",
        sql=sql,
        reason="Schema-aware list/status/date candidate from relevant table columns.",
        selected_tables=[table],
        selected_columns=selected,
        filters=filters,
        confidence=0.66 + (0.06 if filters else 0.0) + (0.04 if order else 0.0),
        warnings=[] if selected else ["No display columns selected; using wildcard."],
    )


def _relationship_join_candidate(
    query: str,
    schema: SchemaIndex,
    top_tables: list[str],
    tokens: QueryTokens,
) -> SchemaAwareSQLCandidate | None:
    path = _find_join_path(schema, top_tables)
    if not path:
        return None
    tables = _tables_from_path(path)
    aliases = {table: f"T{index}" for index, table in enumerate(tables)}
    from_table = tables[0]
    sql_parts = [f"FROM {quote_ident(from_table)} AS {aliases[from_table]}"]
    for edge in path:
        left_table = edge["left_table"]
        right_table = edge["right_table"]
        if right_table not in aliases:
            return None
        right_alias = aliases[right_table]
        left_alias = aliases[left_table]
        sql_parts.append(
            f"JOIN {quote_ident(right_table)} AS {right_alias} "
            f"ON {left_alias}.{quote_ident(edge['left_column'])} = {right_alias}.{quote_ident(edge['right_column'])}"
        )

    display_columns = _join_display_columns(query, schema, tables, aliases, tokens)
    if _asks_count(tokens):
        count_table = next((table for table in reversed(tables) if not schema.tables[table].get("is_bridge")), tables[-1])
        count_column = _primary_id_column(schema, count_table) or _first_id_column(schema, count_table)
        aggregation = f"COUNT(DISTINCT {aliases[count_table]}.{quote_ident(count_column)})" if count_column else "COUNT(*)"
        select_sql = f"{aggregation} AS count"
        selected_columns = [count_column] if count_column else []
    else:
        aggregation = None
        select_sql = ", ".join(
            f"{aliases[table]}.{quote_ident(column)}"
            for table, column in display_columns
        )
        selected_columns = [column for _, column in display_columns]
    sql = f"SELECT {select_sql} {' '.join(sql_parts)} LIMIT 50"
    return SchemaAwareSQLCandidate(
        candidate_id="schema_join_path",
        sql=sql,
        reason="Schema-aware relationship candidate using existing join hints and bridge tables.",
        selected_tables=tables,
        selected_columns=selected_columns,
        join_path=path,
        aggregation=aggregation,
        filters=[],
        confidence=0.86 if _relationship_requested(tokens) else 0.72,
        warnings=[],
    )


def _find_join_path(schema: SchemaIndex, top_tables: list[str]) -> list[dict[str, str]]:
    content_tables = [table for table in top_tables if table in schema.tables and not schema.tables[table].get("is_bridge")]
    for left in content_tables:
        for right in content_tables:
            if left == right:
                continue
            direct = _direct_edge(schema.join_hints, left, right)
            if direct:
                return [_edge_dict(direct, left)]
            bridge = _bridge_path(schema, left, right)
            if bridge:
                return bridge
    return []


def _direct_edge(hints: list[JoinHint], left: str, right: str) -> JoinHint | None:
    for hint in hints:
        if {hint.left_table, hint.right_table} == {left, right}:
            return hint
    return None


def _bridge_path(schema: SchemaIndex, left: str, right: str) -> list[dict[str, str]]:
    for bridge in schema.bridge_tables:
        left_edge = _direct_edge(schema.join_hints, left, bridge)
        right_edge = _direct_edge(schema.join_hints, bridge, right)
        if left_edge and right_edge:
            first = _edge_dict(left_edge, left)
            second = _edge_dict(right_edge, bridge)
            if first["right_table"] == bridge and second["left_table"] == bridge:
                return [first, second]
    return []


def _edge_dict(hint: JoinHint, start_table: str) -> dict[str, str]:
    if hint.left_table == start_table:
        return {
            "left_table": hint.left_table,
            "left_column": hint.left_column,
            "right_table": hint.right_table,
            "right_column": hint.right_column,
            "reason": hint.reason,
        }
    return {
        "left_table": hint.right_table,
        "left_column": hint.right_column,
        "right_table": hint.left_table,
        "right_column": hint.left_column,
        "reason": hint.reason,
    }


def _tables_from_path(path: list[dict[str, str]]) -> list[str]:
    tables = [path[0]["left_table"]]
    for edge in path:
        if edge["right_table"] not in tables:
            tables.append(edge["right_table"])
    return tables


def _display_columns(query: str, columns: list[str], tokens: QueryTokens, *, limit: int = 8) -> list[str]:
    words = set(tokens.words)
    ranked: list[tuple[int, str]] = []
    for column in columns:
        lowered = column.lower()
        column_words = set(re.findall(r"[a-z0-9]+", lowered.replace("_", " ")))
        score = 0
        if words & column_words:
            score += 4
        if any(token in lowered for token in ["name", "title", "label", "display"]):
            score += 3
        if any(token in lowered for token in ["status", "state"]):
            score += 2
        if any(token in lowered for token in ["time", "date", "created", "updated", "modified"]):
            score += 2
        if "id" in lowered:
            score += 1
        if score > 0:
            ranked.append((score, column))
    if not ranked:
        return columns[: min(limit, len(columns))]
    return [column for _, column in sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]]


def _join_display_columns(
    query: str,
    schema: SchemaIndex,
    tables: list[str],
    aliases: dict[str, str],
    tokens: QueryTokens,
) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    for table in tables:
        if schema.tables[table].get("is_bridge"):
            continue
        for column in _display_columns(query, schema.columns_for(table), tokens, limit=4):
            selected.append((table, column))
    return selected[:10]


def _filters_for_table(alias: str, columns: list[str], tokens: QueryTokens) -> list[str]:
    filters: list[str] = []
    entity = next(iter(tokens.quoted_entities or tokens.named_entities), None)
    name_column = _first_column(columns, ["name", "title", "label", "display"])
    if entity and name_column:
        safe = entity.replace("'", "''")
        filters.append(f"LOWER(CAST({alias}.{quote_ident(name_column)} AS VARCHAR)) LIKE LOWER('%{safe}%')")
    status_column = _first_column(columns, ["status", "state"])
    if status_column and tokens.statuses:
        safe_status = tokens.statuses[0].replace("'", "''")
        filters.append(f"LOWER(CAST({alias}.{quote_ident(status_column)} AS VARCHAR)) LIKE LOWER('%{safe_status}%')")
    return filters


def _order_clause(alias: str, columns: list[str], tokens: QueryTokens) -> str:
    if not any(word in tokens.matching_text for word in ["recent", "latest", "newest", "last", "modified", "updated", "created"]):
        return ""
    time_column = _first_column(columns, ["updatedtime", "modified", "createdtime", "date", "time"])
    return f" ORDER BY {alias}.{quote_ident(time_column)} DESC" if time_column else ""


def _asks_count(tokens: QueryTokens) -> bool:
    text = tokens.matching_text
    return any(marker in text for marker in ["how many", "number of", "count", "total"])


def _asks_distinct(tokens: QueryTokens) -> bool:
    text = tokens.matching_text
    return any(marker in text for marker in ["distinct", "unique", "deduplicated", "different"])


def _relationship_requested(tokens: QueryTokens) -> bool:
    text = tokens.matching_text
    return any(marker in text for marker in ["connected", "associated", "related", "mapped", "linked", "relationship", "uses"])


def _primary_id_column(schema: SchemaIndex, table: str) -> str | None:
    return schema.tables.get(table, {}).get("primary_like_id")


def _first_id_column(schema: SchemaIndex, table: str) -> str | None:
    ids = schema.tables.get(table, {}).get("id_columns") or []
    return ids[0] if ids else None


def _first_column(columns: list[str], needles: list[str]) -> str | None:
    for needle in needles:
        normalized_needle = normalize_name(needle)
        for column in columns:
            if normalized_needle in normalize_name(column):
                return column
    return None


def _candidate_is_valid(candidate: SchemaAwareSQLCandidate) -> bool:
    return bool(candidate.validation.get("ok"))


def _compact_probe(probe: dict[str, Any] | None) -> dict[str, Any] | None:
    if probe is None:
        return None
    return {
        "ok": bool(probe.get("ok")),
        "row_count": probe.get("row_count", 0),
        "error": probe.get("error"),
    }


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result
