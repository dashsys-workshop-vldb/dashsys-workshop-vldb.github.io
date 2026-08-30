from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .call_budget import apply_tool_budget
from .evidence_policy import API_SKIP


@dataclass
class PlanOptimizerResult:
    steps: list[Any]
    actions: list[str] = field(default_factory=list)


def optimize_plan_steps(
    steps: list[Any],
    *,
    strategy: str,
    route_type: str,
    api_decision: Any = None,
) -> PlanOptimizerResult:
    actions: list[str] = []
    if api_decision is not None and getattr(api_decision, "mode", None) == API_SKIP:
        before = len(steps)
        steps = [step for step in steps if getattr(step, "action", None) != "api"]
        if len(steps) != before:
            actions.append("removed API steps blocked by API_SKIP")

    deduped: list[Any] = []
    seen_sql: set[str] = set()
    seen_api: set[str] = set()
    for step in steps:
        action = getattr(step, "action", None)
        if action == "sql":
            key = normalize_sql(getattr(step, "sql", "") or "")
            if key in seen_sql:
                actions.append("removed duplicate SQL step")
                continue
            seen_sql.add(key)
        elif action == "api":
            if has_unresolved_placeholder(step) and not has_unresolved_warning(step):
                actions.append(f"removed unresolved API step {getattr(step, 'family', '') or getattr(step, 'url', '')}")
                continue
            key = api_key(step)
            if key in seen_api:
                actions.append(f"removed duplicate API step {getattr(step, 'family', '') or getattr(step, 'url', '')}")
                continue
            seen_api.add(key)
        deduped.append(step)

    max_api_calls = getattr(api_decision, "max_api_calls", None) if api_decision is not None else None
    budgeted, warnings = apply_tool_budget(deduped, strategy=strategy, route_type=route_type, max_api_calls=max_api_calls)
    actions.extend(warnings)
    return PlanOptimizerResult(budgeted, actions)


def normalize_sql(sql: str) -> str:
    return " ".join(sql.strip().rstrip(";").replace('"', "").lower().split())


def api_key(step: Any) -> str:
    return json.dumps(
        {
            "method": getattr(step, "method", ""),
            "url": getattr(step, "url", ""),
            "params": getattr(step, "params", {}),
        },
        sort_keys=True,
        default=str,
    )


def has_unresolved_placeholder(step: Any) -> bool:
    url = str(getattr(step, "url", "") or "")
    if re.search(r"\{[a-zA-Z0-9_]+\}", url):
        return True
    return params_have_placeholder(getattr(step, "params", {}) or {})


def params_have_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(params_have_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(params_have_placeholder(item) for item in value)
    if isinstance(value, str):
        return bool(re.search(r"<[^>]+>|\{[a-zA-Z0-9_]+\}", value))
    return False


def has_unresolved_warning(step: Any) -> bool:
    warnings = getattr(step, "warnings", []) or []
    return any("unresolved_parameter" in str(warning) for warning in warnings)
