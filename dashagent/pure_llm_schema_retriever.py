from __future__ import annotations

import re
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .llm_sql_context_builder import build_llm_sql_context, infer_answer_intent
from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets


TIMESTAMP_ROLE_TERMS = {
    "published_timestamp_columns": ("published", "deployed", "launched", "released"),
    "updated_timestamp_columns": ("updated", "modified", "recent"),
    "created_timestamp_columns": ("created", "new"),
}


def retrieve_schema_context(
    prompt: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog | None = None,
    *,
    max_tables: int = 6,
) -> dict[str, Any]:
    base = build_llm_sql_context(prompt, schema_index, endpoint_catalog, max_tables=max_tables)
    retrieved_tables = _rank_tables(prompt, schema_index, base)
    selected = [item["table"] for item in retrieved_tables[:max_tables]]
    semantic_roles = _semantic_roles(schema_index, selected)
    value_links = _value_links(prompt, schema_index, selected)
    payload = {
        **base,
        "retrieved_tables": retrieved_tables[:max_tables],
        "retrieved_columns": {
            table: _rank_columns(prompt, schema_index.columns_for(table))
            for table in selected
            if schema_index.table_exists(table)
        },
        "join_candidates": schema_index.selected_join_hints(selected)[:16],
        "value_links": value_links,
        "semantic_roles": semantic_roles,
        "confidence": _confidence(retrieved_tables),
        "answer_intent": base.get("answer_intent") or infer_answer_intent(prompt),
    }
    return redact_secrets(payload)


def _rank_tables(prompt: str, schema_index: SchemaIndex, base: dict[str, Any]) -> list[dict[str, Any]]:
    prompt_tokens = set(_tokens(prompt))
    base_scores = {item.get("table"): float(item.get("score") or 0.0) for item in base.get("top_tables", []) if isinstance(item, dict)}
    aliases = base.get("business_term_aliases") if isinstance(base.get("business_term_aliases"), dict) else {}
    rows = []
    for table in schema_index.tables:
        score = base_scores.get(table, 0.0)
        for term, mapped in aliases.items():
            if mapped == table and term in prompt_tokens:
                score += 8.0
        for column in schema_index.columns_for(table):
            normalized = normalize_name(column)
            if any(token and token in normalized for token in prompt_tokens):
                score += 1.0
            if any(marker in normalized for marker in ("id", "name", "status", "state", "time", "date", "count")):
                score += 0.05
        if table in schema_index.bridge_tables:
            score -= 0.5
        rows.append({"table": table, "score": round(score, 4), "is_bridge": table in schema_index.bridge_tables})
    rows.sort(key=lambda item: (-float(item["score"]), item["table"]))
    return rows


def _rank_columns(prompt: str, columns: list[str]) -> list[dict[str, Any]]:
    prompt_l = prompt.lower()
    ranked = []
    for column in columns:
        role = _column_role(column)
        score = 0.0
        normalized = normalize_name(column)
        if role == "id" and re.search(r"\bids?\b", prompt_l):
            score += 5.0
        if role == "name" and any(term in prompt_l for term in ("name", "list", "show", "which")):
            score += 5.0
        if role == "status" and any(term in prompt_l for term in ("status", "state", "active", "failed", "succeeded", "published")):
            score += 5.0
        if role == "timestamp":
            score += _timestamp_score(prompt_l, normalized)
        if any(token in normalized for token in _tokens(prompt)):
            score += 1.0
        ranked.append({"column": column, "role": role, "score": round(score, 4)})
    ranked.sort(key=lambda item: (-float(item["score"]), item["column"]))
    return ranked


def _semantic_roles(schema_index: SchemaIndex, tables: list[str]) -> dict[str, dict[str, list[str]]]:
    roles = {
        "id_columns": {},
        "name_columns": {},
        "status_columns": {},
        "published_timestamp_columns": {},
        "updated_timestamp_columns": {},
        "created_timestamp_columns": {},
        "metric_columns": {},
    }
    for table in tables:
        if not schema_index.table_exists(table):
            continue
        for column in schema_index.columns_for(table):
            normalized = normalize_name(column)
            if normalized == "id" or normalized.endswith("id"):
                roles["id_columns"].setdefault(table, []).append(column)
            if normalized in {"name", "title", "displayname"} or normalized.endswith("name"):
                roles["name_columns"].setdefault(table, []).append(column)
            if "status" in normalized or "state" in normalized:
                roles["status_columns"].setdefault(table, []).append(column)
            if "deployed" in normalized or "published" in normalized:
                roles["published_timestamp_columns"].setdefault(table, []).append(column)
            if "updated" in normalized or "modified" in normalized:
                roles["updated_timestamp_columns"].setdefault(table, []).append(column)
            if "created" in normalized:
                roles["created_timestamp_columns"].setdefault(table, []).append(column)
            if "count" in normalized or "total" in normalized or "member" in normalized or "profile" in normalized:
                roles["metric_columns"].setdefault(table, []).append(column)
    return roles


def _value_links(prompt: str, schema_index: SchemaIndex, tables: list[str]) -> list[dict[str, Any]]:
    links = []
    for value in _quoted_values(prompt):
        candidate_columns = []
        for table in tables:
            for column in schema_index.columns_for(table):
                normalized = normalize_name(column)
                if normalized in {"name", "title", "displayname"} or normalized.endswith("name"):
                    candidate_columns.append({"table": table, "column": column, "role": "name"})
        if candidate_columns:
            links.append({"value": value, "source": "quoted_prompt_text", "candidate_columns": candidate_columns[:8]})
    return links[:8]


def _column_role(column: str) -> str:
    normalized = normalize_name(column)
    if normalized == "id" or normalized.endswith("id"):
        return "id"
    if normalized in {"name", "title", "displayname"} or normalized.endswith("name"):
        return "name"
    if "status" in normalized or "state" in normalized:
        return "status"
    if any(marker in normalized for marker in ("time", "date", "created", "updated", "deployed", "published")):
        return "timestamp"
    if any(marker in normalized for marker in ("count", "total", "member", "profile")):
        return "metric"
    return "other"


def _timestamp_score(prompt_l: str, normalized_column: str) -> float:
    if any(term in prompt_l for term in TIMESTAMP_ROLE_TERMS["published_timestamp_columns"]):
        return 6.0 if ("deployed" in normalized_column or "published" in normalized_column) else 0.5
    if any(term in prompt_l for term in TIMESTAMP_ROLE_TERMS["updated_timestamp_columns"]):
        return 6.0 if ("updated" in normalized_column or "modified" in normalized_column) else 0.5
    if any(term in prompt_l for term in TIMESTAMP_ROLE_TERMS["created_timestamp_columns"]):
        return 6.0 if "created" in normalized_column else 0.5
    if any(term in prompt_l for term in ("when", "date", "time")):
        return 2.0
    return 0.0


def _confidence(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    first = float(rows[0].get("score") or 0.0)
    second = float(rows[1].get("score") or 0.0) if len(rows) > 1 else 0.0
    if first <= 0:
        return 0.0
    return round(min(1.0, max(0.1, (first - second + 1.0) / (first + 1.0))), 4)


def _quoted_values(prompt: str) -> list[str]:
    return [match.group(1) or match.group(2) for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", prompt)]


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-zA-Z0-9]+", text.lower()) if token]
