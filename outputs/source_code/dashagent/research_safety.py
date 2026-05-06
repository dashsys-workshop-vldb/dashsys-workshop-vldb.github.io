from __future__ import annotations

from typing import Any

from .candidate_context_builder import SCHEMA_ALIASES
from .query_family_examples import few_shot_public_overlap_check


def build_research_safety_audit(schema_index: Any, public_examples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    overlap = few_shot_public_overlap_check(public_examples)
    return {
        "public_query_overlap": bool(overlap.get("exact_query_overlap")),
        "gold_sql_overlap": bool(overlap.get("exact_gold_sql_overlap")),
        "public_answer_overlap": bool(overlap.get("public_answer_overlap")),
        "public_entity_overlap": bool(overlap.get("public_entity_overlap")),
        "schema_alias_source": {
            alias: payload.get("source", "general schema alias")
            for alias, payload in SCHEMA_ALIASES.items()
        },
        "join_hint_source": {
            f"{hint.left_table}.{hint.left_column}->{hint.right_table}.{hint.right_column}": _join_source(hint.reason)
            for hint in schema_index.join_hints
        },
        "family_example_source": overlap.get("family_example_source", {}),
        "used_gold_patterns": False,
    }


def _join_source(reason: str) -> str:
    if reason.startswith("Curated:"):
        return "manual general rule"
    if "Matching ID-like" in reason:
        return "schema-level relationship"
    if "Foreign-key-looking" in reason:
        return "naming convention"
    if "bridge" in reason.lower():
        return "bridge-table heuristic"
    return "schema-level relationship"
