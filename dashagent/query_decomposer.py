from __future__ import annotations

import re
from typing import Any

from .query_tokens import QueryTokens


FIELD_REQUEST_RE = re.compile(r"\b(showing|including|include|with)\b", re.IGNORECASE)
SORT_RE = re.compile(r"\b(sorted|order(?:ed)? by|most recently|recent)\b", re.IGNORECASE)
AGG_RE = re.compile(r"\b(count|how many|sum|average|daily|between)\b", re.IGNORECASE)


def should_decompose_query(query: str, tokens: QueryTokens) -> bool:
    lowered = query.lower()
    multi_fields = "," in query and bool(FIELD_REQUEST_RE.search(query))
    join_heavy = sum(domain in tokens.domain_tokens for domain in ("segment_audience", "destination_dataflow", "schema_dataset")) >= 2
    time_range = bool(tokens.date_ranges or ("last" in lowered and any(word in lowered for word in ("days", "months", "weeks"))))
    list_filter_sort = "list" in lowered and bool(SORT_RE.search(query))
    multiple_constraints = len(tokens.quoted_entities) + len(tokens.statuses) + len(tokens.dates) + len(tokens.batch_ids) >= 2
    return bool(multi_fields or join_heavy or time_range or list_filter_sort or multiple_constraints)


def decompose_query(query: str, tokens: QueryTokens, schema_linking: dict[str, Any] | None = None) -> dict[str, Any]:
    active = should_decompose_query(query, tokens)
    if not active:
        return {"active": False, "reason": "simple query; decomposition skipped"}
    required_entities = tokens.quoted_entities + tokens.batch_ids + tokens.schema_ids + tokens.metric_names
    required_filters = tokens.statuses + tokens.dates
    required_aggregations = []
    lowered = query.lower()
    if any(term in lowered for term in ("count", "how many")):
        required_aggregations.append("count")
    if "daily" in lowered or tokens.date_ranges:
        required_aggregations.append("time_range")
    required_sorting = []
    if SORT_RE.search(query):
        required_sorting.append("sort_or_recent")
    required_tables = []
    if schema_linking:
        for link in schema_linking.get("forward_links", [])[:8]:
            table = link.get("table")
            if table and table not in required_tables:
                required_tables.append(table)
    sub_questions = []
    if required_entities:
        sub_questions.append("Ground named entities and identifiers.")
    if required_tables:
        sub_questions.append("Select tables and joins needed for requested fields.")
    if required_filters:
        sub_questions.append("Apply status/date/entity filters.")
    if required_aggregations:
        sub_questions.append("Compute requested aggregation or time-range result.")
    if required_sorting:
        sub_questions.append("Apply requested ordering.")
    if not sub_questions:
        sub_questions.append("Break complex request into SQL planning constraints.")
    return {
        "active": True,
        "sub_questions": sub_questions,
        "required_entities": required_entities,
        "required_tables": required_tables,
        "required_filters": required_filters,
        "required_aggregations": required_aggregations,
        "required_sorting": required_sorting,
        "expected_answer_shape": expected_answer_shape(query, required_aggregations),
    }


def expected_answer_shape(query: str, aggregations: list[str] | None = None) -> str:
    lowered = query.lower()
    aggregations = aggregations or []
    if "count" in aggregations or "how many" in lowered:
        return "scalar_count"
    if "time_range" in aggregations or "daily" in lowered:
        return "time_series"
    if any(word in lowered for word in ("list", "show", "which")):
        return "table_or_list"
    return "short_fact"
