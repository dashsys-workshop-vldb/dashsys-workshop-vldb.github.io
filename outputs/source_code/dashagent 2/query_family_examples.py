from __future__ import annotations

from typing import Any


QUERY_FAMILY_EXAMPLES = [
    {"family": "journey_status", "example": "Find a journey by name placeholder and return status fields.", "source": "generic schema-pattern example"},
    {"family": "destination_mapping", "example": "Join destination and audience bridge tables using placeholder names.", "source": "generic schema-pattern example"},
    {"family": "schema_count", "example": "Count schema records grouped by class placeholder.", "source": "generic schema-pattern example"},
    {"family": "tag_detail", "example": "Call tag endpoint or filter local tag-like metadata for placeholder category.", "source": "generic API-family example"},
    {"family": "merge_policy", "example": "List merge policy records and identify default flag if present.", "source": "generic API-family example"},
    {"family": "segment_jobs", "example": "Filter segment job endpoint by placeholder status.", "source": "generic API-family example"},
    {"family": "batch_files", "example": "Use placeholder batch id to request export batch files endpoint.", "source": "generic API-family example"},
    {"family": "observability_metrics", "example": "Request placeholder metric over placeholder date range.", "source": "generic API-family example"},
]


def examples_for_family(family: str, *, max_examples: int = 2) -> list[dict[str, str]]:
    exact = [item for item in QUERY_FAMILY_EXAMPLES if item["family"] == family]
    return (exact or QUERY_FAMILY_EXAMPLES[:max_examples])[:max_examples]


def few_shot_public_overlap_check(public_examples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    public_examples = public_examples or []
    example_text = "\n".join(item["example"].lower() for item in QUERY_FAMILY_EXAMPLES)
    public_queries = [str(item.get("query", "")).lower() for item in public_examples]
    gold_sql = [str(item.get("gold_sql", "")).lower() for item in public_examples]
    public_answers = [str(item.get("answer", "")).lower() for item in public_examples]
    return {
        "exact_query_overlap": any(query and query in example_text for query in public_queries),
        "exact_gold_sql_overlap": any(sql and sql in example_text for sql in gold_sql),
        "public_answer_overlap": any(answer and answer in example_text for answer in public_answers),
        "public_entity_overlap": False,
        "family_example_source": {item["family"]: item["source"] for item in QUERY_FAMILY_EXAMPLES},
        "example_count": len(QUERY_FAMILY_EXAMPLES),
    }
