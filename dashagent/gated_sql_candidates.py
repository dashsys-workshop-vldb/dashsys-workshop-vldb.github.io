from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .planner import Plan, PlanStep
from .sql_ast_tools import sql_ast_summary
from .validators import SQLValidator


@dataclass(frozen=True)
class SQLCandidate:
    name: str
    sql: str
    source: str
    validation_ok: bool
    ast_valid: bool
    expected_answer_shape: str
    cost_estimate: int
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def hard_case_triggers(
    *,
    candidate_context: dict[str, Any] | None = None,
    validation_failed: bool = False,
    decomposition: dict[str, Any] | None = None,
    value_retrieval: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    context = candidate_context or {}
    schema_linking = context.get("schema_linking", {}) if isinstance(context, dict) else {}
    if schema_linking.get("schema_link_risk") == "high":
        reasons.append("high_schema_link_risk")
    if float(context.get("confidence") or 0.0) < 0.4 and context:
        reasons.append("low_candidate_confidence")
    if float(context.get("score_margin") or 0.0) == 0.0 and context:
        reasons.append("zero_score_margin")
    if validation_failed:
        reasons.append("sql_validation_failed")
    if decomposition and decomposition.get("active"):
        reasons.append("complex_query_decomposition")
    if value_retrieval and value_retrieval.get("match_count", 0) and not value_retrieval.get("used_by_sql", False):
        reasons.append("value_match_not_used_by_sql")
    return reasons


def select_gated_sql_candidate(
    *,
    query: str,
    plan: Plan,
    sql_validator: SQLValidator,
    expected_answer_shape: str = "unknown",
    trigger_reasons: list[str] | None = None,
    max_candidates: int = 3,
) -> dict[str, Any]:
    reasons = trigger_reasons or []
    sql_steps = [step for step in plan.steps if step.action == "sql" and step.sql]
    if not reasons or not sql_steps:
        return {
            "active": False,
            "hard_case_triggered": False,
            "trigger_reasons": reasons,
            "candidate_count": 0,
            "selected_candidate": None,
            "rejected_candidates": [],
            "note": "No hard-case trigger or no SQL step; candidate validation skipped.",
        }
    candidates: list[SQLCandidate] = []
    for index, step in enumerate(sql_steps[:max_candidates]):
        validation = sql_validator.validate(step.sql or "")
        ast = sql_ast_summary(step.sql or "", sql_validator.schema_index)
        ast_valid = bool(ast.get("parsed_ok")) and not ast.get("unknown_tables") and not ast.get("unknown_columns") and not ast.get("destructive_sql_detected")
        rejection = ""
        if not validation.ok:
            rejection = "; ".join(validation.errors)
        elif not ast_valid:
            rejection = "AST table/column validation failed"
        candidates.append(
            SQLCandidate(
                name=f"candidate_{index}",
                sql=step.sql or "",
                source=step.family or "deterministic/template SQL",
                validation_ok=validation.ok,
                ast_valid=ast_valid,
                expected_answer_shape=expected_answer_shape,
                cost_estimate=1,
                rejection_reason=rejection,
            )
        )
    selected = next((candidate for candidate in candidates if candidate.validation_ok and candidate.ast_valid), None)
    return {
        "active": True,
        "hard_case_triggered": True,
        "trigger_reasons": reasons,
        "candidate_count": len(candidates),
        "candidate_sql_sources": [candidate.source for candidate in candidates],
        "validation_results": [candidate.to_dict() for candidate in candidates],
        "selected_candidate": selected.to_dict() if selected else None,
        "rejected_candidates": [candidate.to_dict() for candidate in candidates if candidate is not selected],
        "cost_estimate": sum(candidate.cost_estimate for candidate in candidates),
        "selection_policy": "validation + AST validity + answer-shape + cost; losing candidates are not executed",
        "query": query,
    }
