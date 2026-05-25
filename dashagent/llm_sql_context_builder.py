from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .schema_index import SchemaIndex


INTENT_TOKENS = {
    "COUNT": ("how many", "count", "number of", "total"),
    "LIST": ("list", "show", "which", "names", "ids"),
    "STATUS": ("status", "state", "published", "active", "failed", "succeeded"),
    "DATE": ("when", "date", "time", "recent", "latest", "created", "updated"),
    "DETAIL": ("detail", "metadata", "property", "field", "schema"),
}

DOMAIN_TABLE_HINTS = {
    "campaign": ("dim_campaign",),
    "journey": ("dim_campaign",),
    "audience": ("dim_segment",),
    "segment": ("dim_segment",),
    "destination": ("dim_target",),
    "target": ("dim_target",),
    "schema": ("dim_blueprint", "dim_collection", "dim_property"),
    "dataset": ("dim_collection",),
    "field": ("dim_property",),
    "property": ("dim_property",),
}


def build_llm_sql_context(
    prompt: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog | None = None,
    *,
    answer_intent: str | None = None,
    max_tables: int = 6,
    max_columns_per_table: int = 14,
) -> dict[str, Any]:
    """Build compact schema context for shadow pure-LLM SQL generation.

    This exposes only known schema/catalog facts. It intentionally avoids public
    example IDs, gold answers, and fixed sample-specific SQL templates.
    """
    tokens = _tokens(prompt)
    intent = answer_intent or infer_answer_intent(prompt)
    scored_tables = _rank_tables(tokens, schema_index)
    top_tables = [
        {
            "table": table,
            "score": round(score, 4),
            "is_bridge": bool(schema_index.tables[table].get("is_bridge")),
            "columns": _compact_columns(schema_index.columns_for(table), tokens, max_columns_per_table),
        }
        for table, score in scored_tables[:max_tables]
    ]
    selected = [item["table"] for item in top_tables]
    endpoint_candidates = []
    if endpoint_catalog is not None:
        endpoint_candidates = _endpoint_candidates(prompt, endpoint_catalog)
    return {
        "top_tables": top_tables,
        "columns_by_table": {item["table"]: item["columns"] for item in top_tables},
        "primary_id_columns": {
            table: [schema_index.tables[table].get("primary_like_id")]
            for table in selected
            if schema_index.tables[table].get("primary_like_id")
        },
        "join_hints": schema_index.selected_join_hints(selected)[:16],
        "bridge_tables": [table for table in selected if table in schema_index.bridge_tables],
        "value_hints": _value_hints(prompt),
        "answer_intent": intent,
        "endpoint_candidates": endpoint_candidates,
        "sql_rules": [
            "SELECT only; no writes, DDL, PRAGMA, COPY, INSTALL, LOAD, or multiple statements.",
            "Use only listed table and column names.",
            "Use COUNT DISTINCT for unique entity counts when an ID column is the counted entity.",
            "Join only through listed join hints or bridge tables.",
            "Add LIMIT for broad list/detail queries.",
            "If evidence is missing, say so instead of inventing counts, names, statuses, or timestamps.",
        ],
    }


def infer_answer_intent(prompt: str) -> str:
    lowered = prompt.lower()
    for intent, markers in INTENT_TOKENS.items():
        if any(marker in lowered for marker in markers):
            return intent
    return "DETAIL"


def _rank_tables(tokens: list[str], schema_index: SchemaIndex) -> list[tuple[str, float]]:
    token_counts = Counter(tokens)
    scored: list[tuple[str, float]] = []
    for table, meta in schema_index.tables.items():
        score = 0.0
        table_tokens = _tokens(table)
        score += sum(token_counts[token] for token in table_tokens) * 3.0
        for token, hinted_tables in DOMAIN_TABLE_HINTS.items():
            if token in token_counts and table in hinted_tables:
                score += 6.0
        for column in schema_index.columns_for(table):
            column_tokens = _tokens(column)
            score += sum(token_counts[token] for token in column_tokens)
            if any(part in {"name", "status", "state", "time", "date", "count"} for part in column_tokens):
                score += 0.1
        if meta.get("is_bridge"):
            score -= 0.4
        scored.append((table, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored


def _compact_columns(columns: list[str], tokens: list[str], max_columns: int) -> list[str]:
    token_set = set(tokens)
    priority = []
    rest = []
    for column in columns:
        lowered = column.lower()
        column_tokens = set(_tokens(column))
        if column_tokens & token_set or any(marker in lowered for marker in ("id", "name", "status", "state", "time", "date", "count")):
            priority.append(column)
        else:
            rest.append(column)
    return list(dict.fromkeys(priority + rest))[:max_columns]


def _endpoint_candidates(prompt: str, catalog: EndpointCatalog) -> list[dict[str, Any]]:
    prompt_tokens = set(_tokens(prompt))
    candidates = []
    for endpoint in catalog.endpoints:
        text = " ".join([endpoint.id, endpoint.path, endpoint.use_when, " ".join(endpoint.domains)])
        score = len(prompt_tokens & set(_tokens(text)))
        if score <= 0:
            continue
        candidates.append(
            {
                "endpoint_id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "common_params": endpoint.common_params,
                "domains": endpoint.domains,
                "score": score,
            }
        )
    candidates.sort(key=lambda item: (-int(item["score"]), item["endpoint_id"]))
    return candidates[:8]


def _value_hints(prompt: str) -> list[dict[str, str]]:
    hints = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", prompt):
        value = match.group(1) or match.group(2)
        if value:
            hints.append({"value": value, "source": "quoted_prompt_text"})
    return hints[:8]


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-zA-Z0-9]+", text.lower()) if token]
