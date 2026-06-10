from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .exact_pass_cache import ExactPassCache
from .llm_unified_planner import LLMUnifiedPass, LLMUnifiedPlan, MAX_LLM_OWNED_PASSES
from .pass_graph_gate import PassGraphGateResult


@dataclass
class BudgetLimits:
    max_passes: int = MAX_LLM_OWNED_PASSES
    max_parallelism: int = 4
    max_sql_workers: int = 2
    max_api_workers: int = 2
    max_llm_calls: int = 8
    timeout_seconds: float = 30.0
    max_repair_attempts: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class V2ExecutionOptimizationPlan:
    v2_execution_optimizer_used: bool
    critical_path: list[str]
    stage_pipeline_used: bool
    pass_ids: list[str]
    parallel_groups: list[list[str]]
    dependency_edges: list[list[str]]
    cache_hits: int = 0
    deduped_passes: list[dict[str, Any]] = field(default_factory=list)
    early_stopped_passes: list[dict[str, Any]] = field(default_factory=list)
    budget_limits: dict[str, Any] = field(default_factory=dict)
    budget_exceeded: bool = False
    budget_error: str | None = None
    checkpoint_resume_used: bool = False
    model_cascade_used: bool = False
    backend_semantic_planning_used: bool = False
    model_major_sweep_semantics_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary(self) -> dict[str, Any]:
        return {
            "v2_execution_optimizer_used": self.v2_execution_optimizer_used,
            "critical_path": self.critical_path,
            "stage_pipeline_used": self.stage_pipeline_used,
            "cache_hits": self.cache_hits,
            "deduped_passes": self.deduped_passes,
            "early_stopped_passes": self.early_stopped_passes,
            "budget_limits": self.budget_limits,
            "budget_exceeded": self.budget_exceeded,
            "budget_error": self.budget_error,
            "checkpoint_resume_used": self.checkpoint_resume_used,
            "model_cascade_used": self.model_cascade_used,
            "backend_semantic_planning_used": self.backend_semantic_planning_used,
        }


class PassResultCache(ExactPassCache):
    """Backward-compatible alias for older optimizer tests."""

    def __init__(self, *, api_ttl_seconds: float = 300.0, run_id: str = "run_optimizer") -> None:
        super().__init__(run_id=run_id, api_context_version=f"single_run_no_ttl_{api_ttl_seconds}")

    def store(self, pass_spec: LLMUnifiedPass, source: str, result: dict[str, Any], *, now: float | None = None, checkpoint: bool = False) -> None:  # type: ignore[override]
        pass_result = _tool_result_to_pass_result(pass_spec, source, result, run_id=self.run_id, checkpoint=checkpoint)
        super().store(pass_spec, source=source, pass_result=pass_result)

    def lookup(self, pass_spec: LLMUnifiedPass, source: str, *, target_pass_id: str | None = None, now: float | None = None) -> dict[str, Any] | None:  # type: ignore[override]
        cached_pass_result = super().lookup(pass_spec, source=source, target_pass_id=target_pass_id or pass_spec.pass_id)
        if cached_pass_result is None:
            return None
        original = cached_pass_result.get("cached_tool_result")
        if isinstance(original, dict):
            result = copy.deepcopy(original)
            result["pass_id"] = target_pass_id or pass_spec.pass_id
        else:
            result = copy.deepcopy(cached_pass_result)
        result["cached"] = True
        result["cached_from_pass_id"] = cached_pass_result.get("deduped_from_pass_id")
        result["checkpoint_resume"] = checkpoint = bool(cached_pass_result.get("checkpoint_resume"))
        if checkpoint:
            result["checkpoint_resume"] = True
        return result


class V2ExecutionOptimizer:
    """Backend-only optimizer for LLM-owned V2 pass execution.

    It can prioritize, cache, dedupe, and enforce budgets, but it never changes
    pass semantics, SQL/API candidates, dependencies, or pass membership.
    """

    def __init__(
        self,
        *,
        budget_limits: BudgetLimits | None = None,
        pass_cache: ExactPassCache | None = None,
        run_id: str = "run_optimizer",
    ) -> None:
        self.budget_limits = budget_limits or BudgetLimits()
        self.pass_cache = pass_cache or ExactPassCache(run_id=run_id)
        self.trace: dict[str, Any] = _empty_trace(self.budget_limits)

    def prepare(self, passes: list[LLMUnifiedPass], graph_gate: PassGraphGateResult) -> V2ExecutionOptimizationPlan:
        pass_ids = [item.pass_id for item in passes]
        critical_path = _critical_path(passes)
        groups = _prioritize_groups(graph_gate.parallel_groups, critical_path)
        deduped = _detect_duplicate_passes(passes)
        budget_exceeded = len(passes) > self.budget_limits.max_passes
        budget_error = "max_passes_exceeded" if budget_exceeded else None
        plan = V2ExecutionOptimizationPlan(
            v2_execution_optimizer_used=True,
            critical_path=critical_path,
            stage_pipeline_used=True,
            pass_ids=pass_ids,
            parallel_groups=groups,
            dependency_edges=copy.deepcopy(graph_gate.dependency_edges),
            deduped_passes=deduped,
            budget_limits=self.budget_limits.to_dict(),
            budget_exceeded=budget_exceeded,
            budget_error=budget_error,
            backend_semantic_planning_used=False,
            model_major_sweep_semantics_changed=False,
        )
        self.trace.update(plan.to_summary())
        self.trace["model_major_sweep_semantics_changed"] = False
        return plan

    def lookup_cached_result(self, pass_spec: LLMUnifiedPass, source: str, *, target_pass_id: str | None = None) -> dict[str, Any] | None:
        cached_pass_result = self.pass_cache.lookup(pass_spec, source=source, target_pass_id=target_pass_id or pass_spec.pass_id)
        if cached_pass_result is None:
            return None
        original_tool_result = cached_pass_result.get("cached_tool_result")
        if isinstance(original_tool_result, dict):
            cached = copy.deepcopy(original_tool_result)
            cached["pass_id"] = target_pass_id or pass_spec.pass_id
            cached["cached"] = True
            cached["cached_from_pass_id"] = cached_pass_result.get("deduped_from_pass_id")
            cached["checkpoint_resume"] = bool(cached_pass_result.get("checkpoint_resume"))
            cached["exact_pass_cache_result"] = cached_pass_result
        else:
            cached = cached_pass_result
        self.trace["cache_hits"] = int(self.trace.get("cache_hits", 0) or 0) + 1
        if cached.get("checkpoint_resume"):
            self.trace["checkpoint_resume_used"] = True
        return cached

    def store_result(self, pass_spec: LLMUnifiedPass, source: str, result: dict[str, Any], *, checkpoint: bool = False) -> None:
        pass_result = _tool_result_to_pass_result(pass_spec, source, result, run_id=self.pass_cache.run_id, checkpoint=checkpoint)
        self.pass_cache.store(pass_spec, source=source, pass_result=pass_result)

    def early_stop_decision(self, pass_spec: LLMUnifiedPass, runtime_passes: list[dict[str, Any]]) -> dict[str, Any]:
        if not _is_optional_or_fallback(pass_spec):
            return {"skip": False, "reason": "required_pass"}
        if _has_required_evidence(runtime_passes):
            return {
                "skip": True,
                "reason": "optional_or_fallback_pass_skipped_after_required_evidence",
                "pass_id": pass_spec.pass_id,
            }
        return {"skip": False, "reason": "required_evidence_not_available"}

    def should_cascade_planner(self, plan: LLMUnifiedPlan, graph_gate: PassGraphGateResult | None = None) -> bool:
        should = bool(plan.parse_error or (graph_gate is not None and not graph_gate.passed))
        if should:
            self.trace["model_cascade_used"] = True
        return should


def _empty_trace(limits: BudgetLimits) -> dict[str, Any]:
    return {
        "v2_execution_optimizer_used": True,
        "critical_path": [],
        "stage_pipeline_used": True,
        "cache_hits": 0,
        "deduped_passes": [],
        "early_stopped_passes": [],
        "budget_limits": limits.to_dict(),
        "budget_exceeded": False,
        "checkpoint_resume_used": False,
        "model_cascade_used": False,
        "backend_semantic_planning_used": False,
        "model_major_sweep_semantics_changed": False,
    }


def _critical_path(passes: list[LLMUnifiedPass]) -> list[str]:
    if not passes:
        return []
    by_id = {item.pass_id: item for item in passes}
    memo: dict[str, tuple[int, list[str]]] = {}

    def score(pass_id: str) -> tuple[int, list[str]]:
        if pass_id in memo:
            return memo[pass_id]
        item = by_id[pass_id]
        dep_scores = [score(dep) for dep in item.depends_on if dep in by_id]
        if dep_scores:
            dep_cost, dep_path = max(dep_scores, key=lambda value: value[0])
        else:
            dep_cost, dep_path = 0, []
        total = dep_cost + _pass_cost(item)
        path = [*dep_path, pass_id]
        memo[pass_id] = (total, path)
        return total, path

    _, path = max((score(item.pass_id) for item in passes), key=lambda value: value[0])
    return path


def _pass_cost(item: LLMUnifiedPass) -> int:
    if item.path == "SQL_AND_API":
        return 13
    if item.path == "API":
        return 9
    if item.path == "SQL":
        return 4
    if item.path == "DIRECT":
        return 2
    return 1


def _prioritize_groups(groups: list[list[str]], critical_path: list[str]) -> list[list[str]]:
    priority = {pass_id: index for index, pass_id in enumerate(critical_path)}
    out: list[list[str]] = []
    for group in groups:
        out.append(sorted(group, key=lambda pass_id: priority.get(pass_id, 10_000)))
    return out


def _detect_duplicate_passes(passes: list[LLMUnifiedPass]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], str] = {}
    duplicates: list[dict[str, Any]] = []
    cache = ExactPassCache(run_id="duplicate_detection")
    for item in passes:
        for source in ["sql", "api"]:
            key = cache.key_for(item, source)
            if key is None:
                continue
            compound = (source, key)
            if compound in seen:
                duplicates.append({"pass_id": item.pass_id, "deduped_from": seen[compound], "source": source})
            else:
                seen[compound] = item.pass_id
    return duplicates


def _is_optional_or_fallback(pass_spec: LLMUnifiedPass) -> bool:
    if getattr(pass_spec, "optional", False) or getattr(pass_spec, "fallback", False):
        return True
    raw = " ".join([pass_spec.subtask or "", pass_spec.expected_result or ""]).lower()
    return "optional" in raw or "fallback" in raw


def _has_required_evidence(runtime_passes: list[dict[str, Any]]) -> bool:
    for item in runtime_passes:
        if str(item.get("status") or "").upper() in {"SUCCESS", "EMPTY", "LIVE_EMPTY"}:
            return True
    return False


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _tool_result_to_pass_result(
    pass_spec: LLMUnifiedPass,
    source: str,
    result: dict[str, Any],
    *,
    run_id: str,
    checkpoint: bool = False,
) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    ok = bool(payload.get("ok"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    if source.lower() == "sql":
        status = "SUCCESS" if ok and rows else ("EMPTY" if ok else "FAILED")
        source_result = {"source": "SQL", "status": status, "scope": "LOCAL_SNAPSHOT", "result": {"rows": rows[:5]}, "error": payload.get("error")}
    else:
        parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
        state = str(parsed.get("evidence_state") or "").lower()
        if not ok or state in {"api_error", "malformed_response"}:
            status = "API_ERROR"
        elif "empty" in state:
            status = "LIVE_EMPTY"
        else:
            status = "SUCCESS"
        source_result = {"source": "API", "status": status, "scope": "LIVE_API", "result": {"parsed_evidence": parsed}, "error": payload.get("error")}
    return {
        "run_id": run_id,
        "pass_id": pass_spec.pass_id,
        "global_pass_id": f"{run_id}:{pass_spec.pass_id}",
        "attempt_id": 0,
        "plan_version": 1,
        "subtask": pass_spec.subtask,
        "path": pass_spec.path,
        "status": status,
        "source_results": [source_result],
        "facts": [],
        "caveats": [str(payload.get("error"))] if payload.get("error") else [],
        "cache_hit": False,
        "shared_execution_id": result.get("shared_execution_id"),
        "deduped_from_pass_id": None,
        "stage_history": [],
        "cached_tool_result": copy.deepcopy(result),
        "checkpoint_resume": checkpoint,
    }
