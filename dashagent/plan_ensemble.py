from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from .plan_optimizer import has_unresolved_placeholder, has_unresolved_warning, optimize_plan_steps
from .planner import Plan, PlanStep
from .query_analysis import QueryAnalysis
from .validators import APIValidator, SQLValidator


@dataclass
class PlanCandidate:
    name: str
    plan: Plan
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def compact(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 4),
            "tool_calls": len(self.plan.steps),
        }


@dataclass
class EnsembleSelection:
    plan: Plan
    selected: str
    candidates: list[PlanCandidate]
    actions: list[str] = field(default_factory=list)

    def compact(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "candidate_scores": {candidate.name: round(candidate.score, 4) for candidate in self.candidates},
            "candidate_tool_calls": {candidate.name: len(candidate.plan.steps) for candidate in self.candidates},
        }


def select_plan_candidate(
    *,
    query: str,
    routing: Any,
    base_plan: Plan,
    analysis: QueryAnalysis,
    sql_validator: SQLValidator,
    api_validator: APIValidator,
    strategy: str = "SQL_FIRST_API_VERIFY",
) -> EnsembleSelection:
    candidates = build_candidates(query=query, routing=routing, base_plan=base_plan, analysis=analysis, strategy=strategy)
    for candidate in candidates:
        score_candidate(candidate, analysis, sql_validator, api_validator)
    candidates = sorted(candidates, key=lambda candidate: (-candidate.score, candidate.name != "generic_sql_first"))
    selected = copy.deepcopy(candidates[0].plan)
    selected.optimizer_actions = list(dict.fromkeys([*selected.optimizer_actions, f"ensemble selected {candidates[0].name}"]))
    return EnsembleSelection(
        plan=selected,
        selected=candidates[0].name,
        candidates=candidates,
        actions=[f"selected {candidates[0].name} from {len(candidates)} candidate(s)"],
    )


def build_candidates(
    *,
    query: str,
    routing: Any,
    base_plan: Plan,
    analysis: QueryAnalysis,
    strategy: str,
) -> list[PlanCandidate]:
    candidates = [PlanCandidate("generic_sql_first", copy.deepcopy(base_plan), reasons=["existing validated planner output"])]
    if analysis.fast_path is not None:
        candidates.append(PlanCandidate("fast_path", copy.deepcopy(base_plan), reasons=[f"fast_path={analysis.fast_path.family}"]))
    if analysis.sql_template is not None:
        plan = copy.deepcopy(base_plan)
        for step in plan.steps:
            if step.action == "sql":
                step.sql = analysis.sql_template.sql
                step.allow_full_result = analysis.sql_template.allow_full_result
                step.family = analysis.sql_template.family
                step.purpose = "SQL template candidate selected before execution."
                break
        candidates.append(PlanCandidate("sql_template", plan, reasons=[f"sql_template={analysis.sql_template.family}"]))
    if analysis.lookup_path.family != "unknown":
        plan = copy.deepcopy(base_plan)
        allowed = set(analysis.lookup_path.api_families)
        if allowed:
            filtered = [
                step
                for step in plan.steps
                if step.action != "api" or not step.family or step.family in allowed
            ]
            if filtered:
                plan.steps = filtered
        candidates.append(PlanCandidate("lookup_path", plan, reasons=[f"lookup_path={analysis.lookup_path.family}"]))
    deduped: list[PlanCandidate] = []
    seen = set()
    for candidate in candidates:
        key = plan_signature(candidate.plan)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def score_candidate(
    candidate: PlanCandidate,
    analysis: QueryAnalysis,
    sql_validator: SQLValidator,
    api_validator: APIValidator,
) -> None:
    score = 10.0
    reasons = list(candidate.reasons)
    optimizer = optimize_plan_steps(
        copy.deepcopy(candidate.plan.steps),
        strategy=candidate.plan.strategy,
        route_type=analysis.route_type,
        api_decision=analysis.api_need_decision,
    )
    candidate.plan.steps = optimizer.steps
    if optimizer.actions:
        reasons.extend(optimizer.actions)
        candidate.plan.optimizer_actions = list(dict.fromkeys([*candidate.plan.optimizer_actions, *optimizer.actions]))

    sql_ok = True
    api_ok = True
    unresolved = False
    family_match = False
    forwardable = False
    for step in candidate.plan.steps:
        if step.action == "sql" and step.sql:
            validation = sql_validator.validate(step.sql)
            sql_ok = sql_ok and validation.ok
            score += 2.0 if validation.ok else -8.0
            if step.family and step.family == (analysis.sql_template.family if analysis.sql_template else step.family):
                family_match = True
            if step.sql and any(token in step.sql.lower() for token in ["target_id", "targetid", "schema_id", "schemaid", "campaign_name", "name"]):
                forwardable = True
        elif step.action == "api" and step.method and step.url:
            validation = api_validator.validate(step.method, step.url, step.params, step.headers)
            api_ok = api_ok and validation.ok
            score += 2.0 if validation.ok else -8.0
            if has_unresolved_placeholder(step) and not has_unresolved_warning(step):
                unresolved = True
                score -= 8.0
            if step.family in set(analysis.lookup_path.api_families):
                family_match = True
            if has_unresolved_warning(step) and forwardable:
                score += 0.3

    if sql_ok:
        reasons.append("sql validation passes")
    if api_ok:
        reasons.append("api validation passes")
    if unresolved:
        reasons.append("unresolved placeholder without warning")
    if family_match:
        score += 0.5
        reasons.append("matches predicted family/path")
    score -= 0.08 * len(candidate.plan.steps)
    score -= min(0.5, len(json.dumps(candidate.plan.to_dict(), default=str)) / 10000)
    candidate.score = score
    candidate.reasons = list(dict.fromkeys(reasons))


def plan_signature(plan: Plan) -> str:
    return json.dumps(
        [
            {
                "action": step.action,
                "sql": step.sql,
                "method": step.method,
                "url": step.url,
                "params": step.params,
            }
            for step in plan.steps
        ],
        sort_keys=True,
        default=str,
    )
