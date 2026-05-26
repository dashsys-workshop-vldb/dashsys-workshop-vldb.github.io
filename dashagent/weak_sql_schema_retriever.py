from __future__ import annotations

from typing import Any

from .nlp_generalization_layer import DOMAIN_TERMS, domain_to_table, normalize_prompt_semantics
from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets


DOMAIN_TABLE_ALIASES = {
    "JOURNEY": ("dim_campaign",),
    "SEGMENT": ("dim_segment",),
    "DATASET": ("dim_collection",),
    "SCHEMA": ("dim_blueprint",),
    "DESTINATION": ("dim_target",),
    "CONNECTOR": ("dim_connector",),
    "FIELD": ("dim_property", "hkg_br_segment_property", "hkg_br_blueprint_property"),
    "TAG": (),
    "AUDIT": (),
}


def retrieve_weak_sql_schema_context(
    prompt: str,
    schema_index: SchemaIndex,
    slots: dict[str, Any] | None = None,
    *,
    max_tables: int = 6,
    max_columns_per_table: int = 18,
    max_join_hints: int = 12,
) -> dict[str, Any]:
    """Retrieve compact schema context for weak-model SQL slot compilation.

    The retriever is intentionally lexical and schema-role based. It does not
    use query ids, gold labels, or public-example templates.
    """
    slots = slots if isinstance(slots, dict) else {}
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else normalize_prompt_semantics(prompt)
    domain = str(slots.get("domain") or nlp.get("canonical_domain") or "UNKNOWN").upper()
    prompt_norm = normalize_name(prompt)
    prompt_lower = str(prompt or "").lower()

    table_scores: dict[str, float] = {}
    preferred = _preferred_tables(domain, schema_index)
    for rank, table in enumerate(preferred):
        table_scores[table] = max(table_scores.get(table, 0.0), 5.0 - rank * 0.25)

    for table in schema_index.tables:
        table_norm = normalize_name(table)
        if table_norm and table_norm in prompt_norm:
            table_scores[table] = table_scores.get(table, 0.0) + 2.0
        root = table_norm
        for prefix in ("dim", "fact", "hkg", "br"):
            if root.startswith(prefix):
                root = root[len(prefix) :]
        if root and root in prompt_norm:
            table_scores[table] = table_scores.get(table, 0.0) + 1.25
        for column in schema_index.columns_for(table):
            col_norm = normalize_name(column)
            if col_norm and col_norm in prompt_norm:
                table_scores[table] = table_scores.get(table, 0.0) + 0.4

    for alias_domain, terms in DOMAIN_TERMS.items():
        if any(term in prompt_lower for term in terms):
            for table in _preferred_tables(alias_domain, schema_index):
                table_scores[table] = table_scores.get(table, 0.0) + (1.5 if alias_domain == domain else 0.75)

    ranked_tables = [
        table
        for table, _score in sorted(table_scores.items(), key=lambda item: (-item[1], item[0]))
        if schema_index.table_exists(table)
    ][:max_tables]
    if not ranked_tables:
        ranked_tables = list(schema_index.tables)[:max_tables]

    column_roles = {
        table: _column_roles(schema_index.columns_for(table), max_columns=max_columns_per_table)
        for table in ranked_tables
    }
    timestamp_kind = str(nlp.get("timestamp_semantics") or "")
    timestamp_candidates = {
        table: _timestamp_candidates(column_roles[table], timestamp_kind)
        for table in ranked_tables
    }
    value_links = _value_links(nlp, ranked_tables, column_roles)
    aggregation_candidates = _aggregation_candidates(slots, ranked_tables, column_roles)
    join_candidates = _join_candidates(prompt_lower, ranked_tables, schema_index, max_join_hints=max_join_hints)

    return redact_secrets(
        {
            "retrieved_tables": ranked_tables,
            "retrieved_columns": {
                table: schema_index.columns_for(table)[:max_columns_per_table]
                for table in ranked_tables
            },
            "column_roles": column_roles,
            "join_candidates": join_candidates,
            "value_links": value_links,
            "timestamp_candidates": timestamp_candidates,
            "aggregation_candidates": aggregation_candidates,
            "confidence": round(min(1.0, 0.25 + 0.15 * len(ranked_tables) + (0.25 if preferred else 0.0)), 4),
        }
    )


def _preferred_tables(domain: str, schema_index: SchemaIndex) -> list[str]:
    tables = list(DOMAIN_TABLE_ALIASES.get(str(domain or "").upper(), ()))
    fallback = domain_to_table(domain)
    if fallback and fallback not in tables:
        tables.insert(0, fallback)
    return [table for table in tables if schema_index.table_exists(table)]


def _column_roles(columns: list[str], *, max_columns: int) -> dict[str, list[str]]:
    roles = {
        "id": [],
        "name": [],
        "status": [],
        "timestamp": [],
        "published": [],
        "updated": [],
        "created": [],
        "metric": [],
    }
    for column in columns[:max_columns]:
        norm = normalize_name(column)
        if _metadata_column(norm):
            continue
        if norm == "id" or norm.endswith("id"):
            roles["id"].append(column)
        if any(marker in norm for marker in ("name", "title", "display")):
            roles["name"].append(column)
        if any(marker in norm for marker in ("status", "state", "lifecycle")):
            roles["status"].append(column)
        if any(marker in norm for marker in ("time", "date", "created", "updated", "deployed", "published", "modified")):
            roles["timestamp"].append(column)
        if any(marker in norm for marker in ("deployed", "published", "launch", "release")):
            roles["published"].append(column)
        if any(marker in norm for marker in ("updated", "modified")):
            roles["updated"].append(column)
        if "created" in norm:
            roles["created"].append(column)
        if any(marker in norm for marker in ("count", "total", "member", "profile")):
            roles["metric"].append(column)
    for role, values in list(roles.items()):
        roles[role] = _prioritize_role_columns(role, values)
    return roles


def _timestamp_candidates(roles: dict[str, list[str]], kind: str) -> dict[str, list[str]]:
    published = roles.get("published") or []
    updated = roles.get("updated") or []
    created = roles.get("created") or []
    generic = roles.get("timestamp") or []
    return {
        "published": _dedupe(published + generic),
        "updated": _dedupe(updated + generic),
        "created": _dedupe(created + generic),
        "requested": _dedupe(({"published": published, "updated": updated, "created": created}.get(kind) or []) + generic),
    }


def _value_links(nlp: dict[str, Any], tables: list[str], roles_by_table: dict[str, dict[str, list[str]]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for value in nlp.get("quoted_entities") or []:
        for table in tables:
            for column in roles_by_table.get(table, {}).get("name") or []:
                links.append({"semantic_field": "name", "value": value, "table": table, "column": column, "value_source": "quoted_entity"})
                break
            if links and links[-1]["value"] == value:
                break
    for status in nlp.get("status_terms") or []:
        for table in tables:
            for column in roles_by_table.get(table, {}).get("status") or []:
                links.append({"semantic_field": "status", "value": status, "table": table, "column": column, "value_source": "status_term"})
                break
            if links and links[-1]["semantic_field"] == "status" and links[-1]["value"] == status:
                break
    for date_term in nlp.get("date_terms") or []:
        for table in tables:
            for column in roles_by_table.get(table, {}).get("timestamp") or []:
                links.append({"semantic_field": "date", "value": date_term, "table": table, "column": column, "value_source": "date_term"})
                break
            if links and links[-1]["semantic_field"] == "date" and links[-1]["value"] == date_term:
                break
    return links[:12]


def _aggregation_candidates(slots: dict[str, Any], tables: list[str], roles_by_table: dict[str, dict[str, list[str]]]) -> list[dict[str, str]]:
    intent = str(slots.get("intent") or "").upper()
    if intent != "COUNT":
        return []
    candidates = []
    for table in tables:
        ids = roles_by_table.get(table, {}).get("id") or []
        column = ids[0] if ids else "*"
        candidates.append({"type": "count_distinct" if column != "*" else "count", "table": table, "column": column})
    return candidates


def _join_candidates(prompt_lower: str, tables: list[str], schema_index: SchemaIndex, *, max_join_hints: int = 12) -> list[dict[str, Any]]:
    selected = set(tables)
    relationship_terms = ("connected", "linked", "mapped", "associated", "related", "relationship", "destination", "target")
    include_neighbors = any(term in prompt_lower for term in relationship_terms)
    candidates = []
    for hint in schema_index.join_hints:
        if hint.left_table in selected or hint.right_table in selected or include_neighbors:
            if hint.left_table in schema_index.tables and hint.right_table in schema_index.tables:
                candidates.append(hint.to_dict())
        if len(candidates) >= max_join_hints:
            break
    return candidates


def _metadata_column(normalized: str) -> bool:
    return any(marker in normalized for marker in ("sandbox", "imsorg", "orgid", "acpsystemmetadata", "labels"))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _prioritize_role_columns(role: str, columns: list[str]) -> list[str]:
    if role == "name":
        def score(column: str) -> tuple[int, str]:
            norm = normalize_name(column)
            if norm == "name":
                return (0, norm)
            if norm.endswith("name"):
                return (1, norm)
            if "display" in norm or "title" in norm:
                return (2, norm)
            return (3, norm)

        return sorted(columns, key=score)
    if role == "published":
        return sorted(columns, key=lambda column: (0 if "deployed" in normalize_name(column) else 1, normalize_name(column)))
    if role == "id":
        return sorted(columns, key=lambda column: (0 if normalize_name(column).endswith("id") else 1, len(column), normalize_name(column)))
    return columns
