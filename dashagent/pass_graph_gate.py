from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import json
import re

from .llm_unified_planner import ALLOWED_PASS_PATHS, LLMUnifiedPass, LLMUnifiedPlan, MAX_LLM_OWNED_PASSES
from .trajectory import redact_secrets
from .v2_semantic_alias import validate_unified_plan_semantic_aliases


@dataclass
class PassGraphGateResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    pass_count: int = 0
    pass_ids: list[str] = field(default_factory=list)
    dependency_edges: list[list[str]] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PassGraphGate:
    """Shape-only validation for LLM-owned pass graphs."""

    def __init__(self, *, max_passes: int = MAX_LLM_OWNED_PASSES) -> None:
        self.max_passes = max_passes

    def check(self, plan: LLMUnifiedPlan) -> PassGraphGateResult:
        passes = list(plan.passes or [])
        pass_ids = [item.pass_id for item in passes]
        edges = [[dep, item.pass_id] for item in passes for dep in item.depends_on]
        base = {
            "pass_count": len(passes),
            "pass_ids": pass_ids,
            "dependency_edges": edges,
            "parallel_groups": _parallel_groups(passes),
        }
        if plan.route == "EVIDENCE_PIPELINE" and not passes:
            return _fail("empty_evidence_plan", "EVIDENCE_PIPELINE plans must declare at least one pass.", **base)
        if len(passes) > self.max_passes:
            return _fail("too_many_passes", f"LLM pass count exceeds max_passes={self.max_passes}.", **base)
        if len(set(pass_ids)) != len(pass_ids):
            return _fail("duplicate_pass_id", "LLM pass IDs must be unique.", **base)
        for item in passes:
            error = _pass_shape_error(item)
            if error:
                return _fail(error[0], error[1], **base)
        known = set(pass_ids)
        for dep, pass_id in edges:
            if dep not in known:
                return _fail("unknown_dependency", f"Pass '{pass_id}' depends on unknown pass '{dep}'.", **base)
        for item in passes:
            for ref in _placeholder_pass_refs(item):
                if ref not in known:
                    return _fail("unknown_placeholder_dependency", f"Pass '{item.pass_id}' references unknown placeholder pass '{ref}'.", **base)
        if _has_cycle(passes):
            return _fail("dependency_cycle", "LLM pass dependency graph contains a cycle.", **base)
        alias_gate = validate_unified_plan_semantic_aliases(plan)
        if not alias_gate.passed:
            return _fail(alias_gate.error_type or "invalid_semantic_alias", alias_gate.message or "Invalid semantic alias.", **base)
        for item in passes:
            if item.path == "AGGREGATION_ONLY" and len(passes) == 1:
                return _fail("aggregation_only_without_evidence", "AGGREGATION_ONLY cannot be the only pass.", **base)
        if plan.route == "EVIDENCE_PIPELINE" and not any(item.path in {"SQL", "API", "SQL_AND_API"} for item in passes):
            return _fail("missing_executable_evidence_pass", "EVIDENCE_PIPELINE requires at least one executable SQL/API evidence pass.", **base)
        return PassGraphGateResult(True, **base)


def _fail(error_type: str, message: str, **kwargs: Any) -> PassGraphGateResult:
    return PassGraphGateResult(False, error_type, str(redact_secrets(message))[:500], **kwargs)


def _pass_shape_error(item: LLMUnifiedPass) -> tuple[str, str] | None:
    if not item.pass_id:
        return "malformed_pass", "Pass ID is required."
    if item.path not in ALLOWED_PASS_PATHS:
        return "invalid_path", f"Pass '{item.pass_id}' declares unsupported path '{item.path}'."
    if not isinstance(item.depends_on, list):
        return "malformed_pass", f"Pass '{item.pass_id}' depends_on must be a list."
    has_sql = item.sql is not None
    has_api = item.api_request is not None
    if item.path == "SQL" and (not has_sql or has_api):
        return "path_mismatch", f"Pass '{item.pass_id}' path SQL must contain only sql."
    if item.path == "API" and (not has_api or has_sql):
        return "path_mismatch", f"Pass '{item.pass_id}' path API must contain only api_request."
    if item.path == "SQL_AND_API" and (not has_sql or not has_api):
        return "path_mismatch", f"Pass '{item.pass_id}' path SQL_AND_API must contain both sql and api_request."
    if item.path == "CACHE_ALIAS":
        if has_sql or has_api:
            return "path_mismatch", f"Pass '{item.pass_id}' path CACHE_ALIAS must not contain sql or api_request."
        if not str(getattr(item, "reuse_result_from", "") or "").strip():
            return "invalid_semantic_alias", f"Pass '{item.pass_id}' path CACHE_ALIAS must declare reuse_result_from."
    if item.path in {"DIRECT", "AGGREGATION_ONLY"} and (has_sql or has_api):
        return "path_mismatch", f"Pass '{item.pass_id}' path {item.path} must not contain sql or api_request."
    if item.path == "AGGREGATION_ONLY" and not item.depends_on:
        return "aggregation_without_dependencies", f"Pass '{item.pass_id}' path AGGREGATION_ONLY must depend on earlier passes."
    if item.sql is not None and not str(item.sql.query or "").strip():
        return "malformed_sql", f"Pass '{item.pass_id}' SQL query is missing."
    if item.api_request is not None:
        if not str(item.api_request.method or "").strip() or not str(item.api_request.path or "").strip():
            return "malformed_api_request", f"Pass '{item.pass_id}' API method/path is missing."
        if item.api_request.params is None or not isinstance(item.api_request.params, dict):
            return "malformed_api_request", f"Pass '{item.pass_id}' API params must be an object."
    return None


def _has_cycle(passes: list[LLMUnifiedPass]) -> bool:
    deps = {item.pass_id: set(item.depends_on) for item in passes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(pass_id: str) -> bool:
        if pass_id in visiting:
            return True
        if pass_id in visited:
            return False
        visiting.add(pass_id)
        for dep in deps.get(pass_id, set()):
            if dep in deps and visit(dep):
                return True
        visiting.remove(pass_id)
        visited.add(pass_id)
        return False

    return any(visit(item.pass_id) for item in passes)


def _parallel_groups(passes: list[LLMUnifiedPass]) -> list[list[str]]:
    pending = list(passes)
    complete: set[str] = set()
    groups: list[list[str]] = []
    while pending:
        ready = [item for item in pending if all(dep in complete for dep in item.depends_on)]
        if not ready:
            groups.append([item.pass_id for item in pending])
            break
        parallel_ready = [item for item in ready if item.can_run_parallel]
        sequential_ready = [item for item in ready if item not in parallel_ready]
        if parallel_ready:
            groups.append([item.pass_id for item in parallel_ready])
            for item in parallel_ready:
                complete.add(item.pass_id)
                pending.remove(item)
        for item in sequential_ready:
            groups.append([item.pass_id])
            complete.add(item.pass_id)
            pending.remove(item)
    return groups


PLACEHOLDER_PASS_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\.result\.")


def _placeholder_pass_refs(item: LLMUnifiedPass) -> list[str]:
    text = json.dumps(item.to_dict(), sort_keys=True, default=str)
    return [match.group(1) for match in PLACEHOLDER_PASS_RE.finditer(text)]
