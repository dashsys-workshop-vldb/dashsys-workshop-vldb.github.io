from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .answer_shape import propose_answer_shape_candidate
from .evidence_policy import API_ONLY_FAMILIES, API_REQUIRED, API_SKIP, explicitly_live


@dataclass(frozen=True)
class SqlOnlyApiSkipDecision:
    skip: bool
    reason: str
    sql_satisfies_answer_shape: bool
    api_score_may_be_required: bool
    prior_api_was_noop: bool
    answer_shape: str | None = None
    api_family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skip": self.skip,
            "reason": self.reason,
            "sql_satisfies_answer_shape": self.sql_satisfies_answer_shape,
            "api_score_may_be_required": self.api_score_may_be_required,
            "prior_api_was_noop": self.prior_api_was_noop,
            "answer_shape": self.answer_shape,
            "api_family": self.api_family,
        }


def should_skip_api_with_sql_evidence(
    *,
    query: str,
    prompt_route: Any,
    routing: Any,
    analysis: Any,
    api_step: Any,
    tool_results: list[dict[str, Any]],
    prior_strict_row: dict[str, Any] | None = None,
) -> SqlOnlyApiSkipDecision:
    """Conservative final guard for SQL-only queries with already-sufficient SQL evidence.

    The guard is intentionally stricter than "SQL has an answer": it refuses to
    skip when the planner/query family may need API evidence. Offline strict
    diagnostics can prove a prior dry-run API was no-op, but packaged runtime
    normally lacks that row-level diagnostic and therefore keeps the API.
    """

    api_family = str(getattr(api_step, "family", "") or "")
    shape = propose_answer_shape_candidate(query, tool_results)
    sql_satisfies = _sql_result_present(tool_results) and shape.supported and not shape.unavailable_fields
    if not sql_satisfies:
        return SqlOnlyApiSkipDecision(
            skip=False,
            reason="SQL evidence does not fully satisfy the requested answer shape.",
            sql_satisfies_answer_shape=False,
            api_score_may_be_required=True,
            prior_api_was_noop=False,
            answer_shape=shape.answer_shape,
            api_family=api_family or None,
        )

    may_need_api, api_reason = api_score_may_be_required(
        query=query,
        prompt_route=prompt_route,
        routing=routing,
        analysis=analysis,
        api_family=api_family,
    )
    prior_noop = prior_api_was_unnecessary_noop(prior_strict_row)
    if may_need_api and not prior_noop:
        return SqlOnlyApiSkipDecision(
            skip=False,
            reason=f"API evidence may be required for this query family: {api_reason}",
            sql_satisfies_answer_shape=True,
            api_score_may_be_required=True,
            prior_api_was_noop=False,
            answer_shape=shape.answer_shape,
            api_family=api_family or None,
        )

    return SqlOnlyApiSkipDecision(
        skip=True,
        reason="SQL evidence fully answers the requested shape and API evidence is not required or was proven no-op/dry-run-only by diagnostics.",
        sql_satisfies_answer_shape=True,
        api_score_may_be_required=may_need_api,
        prior_api_was_noop=prior_noop,
        answer_shape=shape.answer_shape,
        api_family=api_family or None,
    )


def api_score_may_be_required(
    *,
    query: str,
    prompt_route: Any,
    routing: Any,
    analysis: Any,
    api_family: str | None = None,
) -> tuple[bool, str]:
    lowered = query.lower()
    if explicitly_live(lowered):
        return True, "query explicitly asks for live/platform/status/API evidence"
    if bool(getattr(prompt_route, "requires_api", False)):
        return True, "prompt router requires API"
    if str(getattr(routing, "route_type", "")) in {"API_ONLY", "SQL_THEN_API", "SQL_AND_API_COMPARE", "API_THEN_SQL"}:
        return True, f"route_type={getattr(routing, 'route_type', '')}"
    decision = getattr(analysis, "api_need_decision", None)
    if getattr(decision, "mode", None) == API_REQUIRED:
        return True, "evidence policy is API_REQUIRED"
    families = set(getattr(decision, "allowed_api_families", []) or [])
    if api_family:
        families.add(api_family)
    if families.intersection(API_ONLY_FAMILIES):
        return True, "API-only family matched"
    if getattr(decision, "mode", None) == API_SKIP:
        return False, "evidence policy already allows API_SKIP"
    return False, "no required API signal after conservative checks"


def prior_api_was_unnecessary_noop(prior_strict_row: dict[str, Any] | None) -> bool:
    if not prior_strict_row:
        return False
    if int(prior_strict_row.get("api_call_count") or prior_strict_row.get("tool_call_count") or 0) <= 0:
        return True
    api_score = prior_strict_row.get("api_score")
    if api_score is not None and float(api_score or 0.0) <= 0:
        return True
    reason = str(prior_strict_row.get("api_reason") or "").lower()
    return "no gold api" in reason or "unscored" in reason or "no api supplied" in reason


def _sql_result_present(tool_results: list[dict[str, Any]]) -> bool:
    for result in tool_results:
        if result.get("type") != "sql":
            continue
        payload = result.get("payload") or {}
        if payload.get("ok"):
            return True
    return False
