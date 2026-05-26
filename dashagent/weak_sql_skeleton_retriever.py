from __future__ import annotations

from typing import Any

from .trajectory import redact_secrets


SQL_SKELETONS: list[dict[str, Any]] = [
    {
        "skeleton_id": "count_distinct_entity",
        "intent": "COUNT",
        "when_to_use": "how many unique entities or local rows by entity identity",
        "semantic_slots_required": ["entity_table", "entity_id_column"],
        "sql_shape": "SELECT COUNT(DISTINCT T.id_col) AS count FROM entity_table T ...",
        "common_mistakes": ["do not count bridge rows", "do not use name column for distinct count"],
    },
    {
        "skeleton_id": "count_entity",
        "intent": "COUNT",
        "when_to_use": "how many rows when no stable entity id column exists",
        "semantic_slots_required": ["entity_table"],
        "sql_shape": "SELECT COUNT(*) AS count FROM entity_table T ...",
        "common_mistakes": ["do not select non-aggregated columns with count"],
    },
    {
        "skeleton_id": "list_entity",
        "intent": "LIST",
        "when_to_use": "list names, ids, or display values for local entities",
        "semantic_slots_required": ["entity_table", "id_or_name_columns"],
        "sql_shape": "SELECT T.id_col, T.name_col FROM entity_table T ... LIMIT 50",
        "common_mistakes": ["include requested id/name columns", "avoid metadata-only columns"],
    },
    {
        "skeleton_id": "status_list",
        "intent": "STATUS",
        "when_to_use": "status or state questions about local entities",
        "semantic_slots_required": ["entity_table", "status_column"],
        "sql_shape": "SELECT T.name_col, T.status_col FROM entity_table T WHERE ... LIMIT 50",
        "common_mistakes": ["use status/state/lifecycle column", "do not use timestamp column as status"],
    },
    {
        "skeleton_id": "date_when_query",
        "intent": "DATE",
        "when_to_use": "when/date/published/created/updated questions",
        "semantic_slots_required": ["entity_table", "timestamp_column"],
        "sql_shape": "SELECT T.name_col, T.timestamp_col FROM entity_table T WHERE T.name_col = ... LIMIT 50",
        "common_mistakes": ["published/deployed asks for deployed/published timestamp", "do not add status filter for a date word"],
    },
    {
        "skeleton_id": "relationship_join",
        "intent": "RELATIONSHIP",
        "when_to_use": "connected, linked, mapped, associated, or related entity questions",
        "semantic_slots_required": ["left_entity_table", "bridge_or_join_hint", "right_entity_table"],
        "sql_shape": "SELECT L.name_col, R.name_col FROM left_table L JOIN bridge B ... JOIN right_table R ...",
        "common_mistakes": ["only use known join hints", "do not make bridge table the primary answer table"],
    },
    {
        "skeleton_id": "entity_detail_lookup",
        "intent": "DETAIL",
        "when_to_use": "lookup attributes for one named local entity",
        "semantic_slots_required": ["entity_table", "name_column"],
        "sql_shape": "SELECT requested_columns FROM entity_table T WHERE T.name_col = ... LIMIT 50",
        "common_mistakes": ["include a name/id filter for quoted entities"],
    },
    {
        "skeleton_id": "zero_row_safe_lookup",
        "intent": "DETAIL",
        "when_to_use": "when a named entity may not exist and the answer must remain grounded",
        "semantic_slots_required": ["entity_table", "name_column"],
        "sql_shape": "SELECT requested_columns FROM entity_table T WHERE T.name_col = ... LIMIT 50",
        "common_mistakes": ["if no rows return, say no matching SQL records"],
    },
]


def retrieve_sql_skeletons(slots: dict[str, Any] | None, *, limit: int = 3) -> list[dict[str, Any]]:
    slots = slots if isinstance(slots, dict) else {}
    intent = str(slots.get("intent") or "").upper()
    aggregation = str(slots.get("aggregation") or "").lower()
    relationship = slots.get("relationship") if isinstance(slots.get("relationship"), dict) else {}
    scored: list[tuple[int, dict[str, Any]]] = []
    for skeleton in SQL_SKELETONS:
        score = 0
        if skeleton["intent"] == intent:
            score += 4
        if intent == "COUNT" and aggregation == "count_distinct" and skeleton["skeleton_id"] == "count_distinct_entity":
            score += 2
        if relationship.get("needed") and skeleton["skeleton_id"] == "relationship_join":
            score += 3
        if skeleton["skeleton_id"] == "zero_row_safe_lookup":
            score -= 1
        scored.append((score, skeleton))
    selected = [item for _score, item in sorted(scored, key=lambda pair: (-pair[0], pair[1]["skeleton_id"]))[:limit]]
    return redact_secrets(selected)
