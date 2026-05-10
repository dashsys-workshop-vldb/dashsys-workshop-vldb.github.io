from __future__ import annotations

from typing import Any

from sqlglot import exp
from sqlglot.errors import ParseError

from .query_tokens import extract_query_tokens
from .schema_index import SchemaIndex
from .sql_ast_tools import parse_sql_ast, sql_ast_summary


def rank_sql_candidate_ast(
    sql: str,
    schema_index: SchemaIndex,
    *,
    query: str = "",
    value_matches: list[dict[str, Any]] | None = None,
    expected_answer_shape: str | None = None,
) -> dict[str, Any]:
    summary = sql_ast_summary(sql, schema_index)
    metrics = _ast_metrics(sql)
    query_family_match = _query_family_match(query, metrics, expected_answer_shape)
    schema_link_coverage = _schema_link_coverage(summary)
    value_match_coverage = _value_match_coverage(sql, value_matches or [])
    answer_shape_match = query_family_match
    ast_quality_score = _quality_score(summary, metrics, query_family_match, schema_link_coverage, value_match_coverage)
    return {
        "parsed_ok": summary.get("parsed_ok", False),
        "selected_tables": summary.get("selected_tables", []),
        "selected_columns": summary.get("selected_columns", []),
        "unknown_tables": summary.get("unknown_tables", []),
        "unknown_columns": summary.get("unknown_columns", []),
        "destructive_sql_detected": summary.get("destructive_sql_detected", False),
        "join_count": metrics["join_count"],
        "aggregation_count": metrics["aggregation_count"],
        "filter_count": metrics["filter_count"],
        "limit_present": metrics["limit_present"],
        "query_family_match": query_family_match,
        "schema_link_coverage": schema_link_coverage,
        "value_match_coverage": value_match_coverage,
        "answer_shape_match": answer_shape_match,
        "ast_quality_score": ast_quality_score,
    }


def _ast_metrics(sql: str) -> dict[str, Any]:
    try:
        tree = parse_sql_ast(sql)
    except ParseError:
        return {"join_count": 0, "aggregation_count": 0, "filter_count": 0, "limit_present": False}
    aggregation_count = sum(1 for _ in tree.find_all(exp.AggFunc))
    aggregation_count += sum(1 for node in tree.find_all(exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max))
    return {
        "join_count": sum(1 for _ in tree.find_all(exp.Join)),
        "aggregation_count": aggregation_count,
        "filter_count": sum(1 for _ in tree.find_all(exp.Where, exp.Having)),
        "limit_present": any(True for _ in tree.find_all(exp.Limit)),
    }


def _query_family_match(query: str, metrics: dict[str, Any], expected_answer_shape: str | None) -> bool:
    tokens = extract_query_tokens(query or "")
    text = tokens.matching_text
    if expected_answer_shape and expected_answer_shape not in {"unknown", "list"}:
        if "count" in expected_answer_shape:
            return metrics["aggregation_count"] > 0
    if any(word in text for word in ["how many", "count", "number of"]):
        return metrics["aggregation_count"] > 0
    if any(word in text for word in ["list", "show", "which", "what"]):
        return True
    return True


def _schema_link_coverage(summary: dict[str, Any]) -> float:
    if not summary.get("parsed_ok"):
        return 0.0
    tables = summary.get("selected_tables") or []
    unknown = (summary.get("unknown_tables") or []) + (summary.get("unknown_columns") or [])
    if not tables:
        return 0.5 if not unknown else 0.0
    return 1.0 if not unknown else max(0.0, 1.0 - len(unknown) / max(len(tables), 1))


def _value_match_coverage(sql: str, value_matches: list[dict[str, Any]]) -> float:
    if not value_matches:
        return 1.0
    lowered = sql.lower()
    used = 0
    for match in value_matches:
        value = str(match.get("value") or match.get("matched_value") or "").lower()
        if value and value in lowered:
            used += 1
    return round(used / len(value_matches), 4) if value_matches else 1.0


def _quality_score(
    summary: dict[str, Any],
    metrics: dict[str, Any],
    query_family_match: bool,
    schema_link_coverage: float,
    value_match_coverage: float,
) -> float:
    score = 0.0
    if summary.get("parsed_ok"):
        score += 0.35
    if not summary.get("destructive_sql_detected"):
        score += 0.15
    score += 0.25 * schema_link_coverage
    score += 0.15 * value_match_coverage
    if query_family_match:
        score += 0.10
    if metrics.get("limit_present"):
        score -= 0.02
    return round(max(0.0, min(1.0, score)), 4)
