from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MULTI_CALL_API_FAMILIES = {
    "audience_by_destination_id",
    "batch_details",
    "batch_export_files",
    "datasets_by_schema",
    "destination_flows",
    "schema_registry_by_id",
    "tag_categories",
    "tags_by_uncategorized_category",
}


@dataclass(frozen=True)
class ToolBudget:
    max_sql_calls: int
    max_api_calls: int
    max_total_tool_calls: int


def budget_for_strategy(strategy: str, api_families: list[str] | None = None, max_api_calls: int | None = None) -> ToolBudget:
    api_families = api_families or []
    if strategy == "SQL_FIRST_API_VERIFY":
        family_max = 2 if any(family in MULTI_CALL_API_FAMILIES for family in api_families) else 1
        api_max = min(max_api_calls if max_api_calls is not None else family_max, family_max)
        return ToolBudget(max_sql_calls=1, max_api_calls=api_max, max_total_tool_calls=1 + api_max)
    if strategy == "TEMPLATE_FIRST":
        family_max = 2 if any(family in MULTI_CALL_API_FAMILIES for family in api_families) else 1
        return ToolBudget(max_sql_calls=1, max_api_calls=family_max, max_total_tool_calls=1 + family_max)
    if strategy == "LLM_FREE_AGENT_BASELINE":
        return ToolBudget(max_sql_calls=1, max_api_calls=2, max_total_tool_calls=3)
    return ToolBudget(max_sql_calls=1, max_api_calls=1, max_total_tool_calls=2)


def apply_tool_budget(
    steps: list[Any],
    *,
    strategy: str,
    route_type: str,
    max_api_calls: int | None = None,
) -> tuple[list[Any], list[str]]:
    api_families = [getattr(step, "family", None) for step in steps if getattr(step, "action", None) == "api"]
    budget = budget_for_strategy(strategy, [family for family in api_families if family], max_api_calls)
    kept = []
    warnings = []
    sql_seen = 0
    api_seen = 0

    for step in steps:
        action = getattr(step, "action", None)
        if action == "sql":
            sql_seen += 1
            if sql_seen <= budget.max_sql_calls or route_type == "API_ONLY":
                kept.append(step)
            else:
                warnings.append("Dropped extra SQL step due to tool-call budget.")
            continue
        if action == "api":
            api_seen += 1
            if api_seen <= budget.max_api_calls:
                kept.append(step)
            else:
                warnings.append(f"Dropped optional API step {getattr(step, 'family', None) or getattr(step, 'url', '')} due to tool-call budget.")
            continue
        kept.append(step)

    while count_tool_steps(kept) > budget.max_total_tool_calls:
        removed = False
        for index in range(len(kept) - 1, -1, -1):
            if getattr(kept[index], "action", None) == "api":
                dropped = kept.pop(index)
                warnings.append(f"Dropped API step {getattr(dropped, 'family', None) or getattr(dropped, 'url', '')} to respect total tool-call budget.")
                removed = True
                break
        if not removed:
            break
    return kept, warnings


def count_tool_steps(steps: list[Any]) -> int:
    return sum(1 for step in steps if getattr(step, "action", None) in {"sql", "api"})
