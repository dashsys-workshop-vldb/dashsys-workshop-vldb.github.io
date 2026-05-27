from __future__ import annotations

from typing import Any


FORBIDDEN_RUNTIME_KEYS = {
    "category",
    "tags",
    "domain_family",
    "difficulty",
    "split",
    "gold",
    "gold_answer",
    "gold_sql",
    "gold_api",
    "oracle",
    "oracle_sql",
    "oracle_api",
    "expected_trace",
    "expected_observable_trace",
    "expected_tool_calls",
    "required_facts",
    "forbidden_claims",
}

ALLOWED_RUNTIME_KEYS = {
    "query",
    "prompt",
    "query_id",
    "prompt_id",
    "strategy",
    "output_dir",
    "runtime_features",
    "tool_results",
    "checkpoints",
}


def assert_runtime_input_isolated(payload: dict[str, Any]) -> None:
    keys = set(payload)
    forbidden = sorted(keys & FORBIDDEN_RUNTIME_KEYS)
    if forbidden:
        raise ValueError(f"Runtime input contains forbidden evaluation-only fields: {forbidden}")
    suspicious = sorted(
        key
        for key in keys
        if key not in ALLOWED_RUNTIME_KEYS and any(token in key.lower() for token in ("gold", "oracle", "expected", "category", "tag"))
    )
    if suspicious:
        raise ValueError(f"Runtime input contains suspicious evaluation-only fields: {suspicious}")


def runtime_guard_checkpoint(*, strategy: str, query_id: str | None, query: str) -> dict[str, Any]:
    assert_runtime_input_isolated({"query": query, "query_id": query_id, "strategy": strategy})
    return {
        "runtime_input_fields": ["query", "query_id", "strategy"],
        "runtime_gold_visible": False,
        "category_tags_visible": False,
        "oracle_sql_visible": False,
        "expected_trace_visible": False,
        "prompt_id_specific_branching": False,
        "query_id_specific_branching": False,
    }


def score_provenance_runtime_checkpoint(*, strategy: str, score_source: str = "runtime_candidate") -> dict[str, Any]:
    return {
        "strategy": strategy,
        "score_source": score_source,
        "real_agent_execution": True,
        "synthetic_trace": False,
        "runtime_gold_visible": False,
        "promotion_eligible": False,
        "organizer_equivalent": False,
        "promotion_judgment_run": False,
    }
