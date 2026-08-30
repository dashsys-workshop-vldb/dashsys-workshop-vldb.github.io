from __future__ import annotations

import re
from typing import Any

from .schema_index import normalize_name
from .trajectory import redact_secrets


def retrieve_sql_examples(
    prompt: str,
    retrieval_context: dict[str, Any],
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Return schema-generic SQL skeletons for pure-LLM text-to-SQL prompting."""

    intent = str(retrieval_context.get("answer_intent") or _infer_intent(prompt)).upper()
    roles = retrieval_context.get("semantic_roles") if isinstance(retrieval_context.get("semantic_roles"), dict) else {}
    tables = [str(item.get("table")) for item in retrieval_context.get("retrieved_tables", []) if isinstance(item, dict)]
    primary_table = tables[0] if tables else "entity_table"
    examples = _example_bank(primary_table, roles)
    scored = []
    for example in examples:
        score = 0.0
        if intent in example.get("answer_intents", []):
            score += 4.0
        for role in example.get("schema_roles", []):
            if _role_is_available(role, roles, primary_table):
                score += 1.0
        if any(token in str(example.get("natural_language_pattern", "")).lower() for token in _tokens(prompt)):
            score += 0.5
        scored.append((score, example))
    scored.sort(key=lambda item: (-item[0], item[1]["natural_language_pattern"]))
    return redact_secrets(
        [
            {
                "natural_language_pattern": item["natural_language_pattern"],
                "sql_skeleton": item["sql_skeleton"],
                "schema_roles": item["schema_roles"],
                "when_to_use": item["when_to_use"],
                "when_not_to_use": item["when_not_to_use"],
            }
            for _, item in scored[: max(1, limit)]
        ]
    )


def _example_bank(primary_table: str, roles: dict[str, Any]) -> list[dict[str, Any]]:
    id_col = _first_role_column(roles, "id_columns", primary_table) or "entity_id"
    name_col = _first_role_column(roles, "name_columns", primary_table) or "name"
    status_col = _first_role_column(roles, "status_columns", primary_table) or "status"
    created_col = _first_role_column(roles, "created_timestamp_columns", primary_table) or "createdTime"
    updated_col = _first_role_column(roles, "updated_timestamp_columns", primary_table) or "updatedTime"
    published_col = _first_role_column(roles, "published_timestamp_columns", primary_table) or "publishedTime"
    return [
        {
            "natural_language_pattern": "count entities, optionally filtered by status or name",
            "sql_skeleton": f'SELECT COUNT(DISTINCT "{id_col}") AS count FROM "{primary_table}" WHERE "{status_col}" = ?',
            "schema_roles": ["entity_table", "id_column", "status_column"],
            "answer_intents": ["COUNT"],
            "when_to_use": "Use for how many, number of, count, or total questions over one entity table.",
            "when_not_to_use": "Do not use for list, date, or status questions unless the prompt asks for a count.",
        },
        {
            "natural_language_pattern": "list entity IDs and names",
            "sql_skeleton": f'SELECT "{id_col}", "{name_col}" FROM "{primary_table}" LIMIT ?',
            "schema_roles": ["entity_table", "id_column", "name_column"],
            "answer_intents": ["LIST", "DETAIL"],
            "when_to_use": "Use for list, show, which, names, or IDs questions.",
            "when_not_to_use": "Do not use when the prompt asks only for a scalar count.",
        },
        {
            "natural_language_pattern": "lookup entity status by quoted or named entity",
            "sql_skeleton": f'SELECT "{name_col}", "{status_col}" FROM "{primary_table}" WHERE "{name_col}" = ? LIMIT ?',
            "schema_roles": ["entity_table", "name_column", "status_column"],
            "answer_intents": ["STATUS", "DETAIL"],
            "when_to_use": "Use for status or state questions about a named entity.",
            "when_not_to_use": "Do not use if no status-like column exists.",
        },
        {
            "natural_language_pattern": "lookup created timestamp by named entity",
            "sql_skeleton": f'SELECT "{name_col}", "{created_col}" FROM "{primary_table}" WHERE "{name_col}" = ? LIMIT ?',
            "schema_roles": ["entity_table", "name_column", "created_timestamp_column"],
            "answer_intents": ["DATE"],
            "when_to_use": "Use when the prompt asks when something was created or first added.",
            "when_not_to_use": "Do not use for published, deployed, or updated wording.",
        },
        {
            "natural_language_pattern": "lookup updated timestamp by named entity",
            "sql_skeleton": f'SELECT "{name_col}", "{updated_col}" FROM "{primary_table}" WHERE "{name_col}" = ? LIMIT ?',
            "schema_roles": ["entity_table", "name_column", "updated_timestamp_column"],
            "answer_intents": ["DATE"],
            "when_to_use": "Use when the prompt asks when something was updated or modified.",
            "when_not_to_use": "Do not use for published, deployed, launched, or released wording.",
        },
        {
            "natural_language_pattern": "lookup published or deployed timestamp by named entity",
            "sql_skeleton": f'SELECT "{name_col}", "{published_col}" FROM "{primary_table}" WHERE "{name_col}" = ? LIMIT ?',
            "schema_roles": ["entity_table", "name_column", "published_timestamp_column"],
            "answer_intents": ["DATE"],
            "when_to_use": "Use when the prompt asks when something was published, deployed, launched, or released.",
            "when_not_to_use": "Do not use for generic updated or modified wording.",
        },
    ]


def _first_role_column(roles: dict[str, Any], role_key: str, table: str) -> str | None:
    by_table = roles.get(role_key) if isinstance(roles.get(role_key), dict) else {}
    values = by_table.get(table) if isinstance(by_table, dict) else None
    if isinstance(values, list) and values:
        return str(values[0])
    for candidate in by_table.values() if isinstance(by_table, dict) else []:
        if isinstance(candidate, list) and candidate:
            return str(candidate[0])
    return None


def _role_is_available(role: str, roles: dict[str, Any], table: str) -> bool:
    role_map = {
        "id_column": "id_columns",
        "name_column": "name_columns",
        "status_column": "status_columns",
        "created_timestamp_column": "created_timestamp_columns",
        "updated_timestamp_column": "updated_timestamp_columns",
        "published_timestamp_column": "published_timestamp_columns",
    }
    key = role_map.get(role)
    if role == "entity_table":
        return bool(table)
    if not key:
        return False
    return bool(_first_role_column(roles, key, table))


def _infer_intent(prompt: str) -> str:
    prompt_l = prompt.lower()
    if re.search(r"\b(how many|number of|count|total)\b", prompt_l):
        return "COUNT"
    if re.search(r"\bwhen\b|\bdate\b|published|deployed|created|updated", prompt_l):
        return "DATE"
    if re.search(r"\bstatus\b|\bstate\b|active|inactive|failed|succeeded", prompt_l):
        return "STATUS"
    if re.search(r"\blist\b|\bshow\b|\bwhich\b|\bnames?\b|\bids?\b", prompt_l):
        return "LIST"
    return "DETAIL"


def _tokens(text: str) -> list[str]:
    return [normalize_name(token) for token in re.split(r"[^a-zA-Z0-9]+", text.lower()) if token]
