from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .llm_unified_planner import LLMUnifiedPass
from .pass_graph_gate import PassGraphGateResult


PIPELINE_STAGES = [
    "PLAN_READY",
    "DEPENDENCY_READY",
    "SQL_API_GATE",
    "EXECUTE",
    "NORMALIZE_PASS_RESULT",
    "EVIDENCEBUS_APPEND",
    "RESULTBUNDLE_APPEND",
    "READY_FOR_FINAL_COMPOSITION",
]


@dataclass
class V2PipelineSchedule:
    v2_pipeline_scheduler_used: bool
    pipeline_stage_count: int
    max_parallelism: int
    max_sql_workers: int
    max_api_workers: int
    max_observed_parallelism: int
    max_observed_sql_workers: int
    max_observed_api_workers: int
    parallel_groups: list[list[str]]
    dependency_edges: list[list[str]]
    stage_events: list[dict[str, Any]] = field(default_factory=list)
    pass_stage_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    passes_completed: list[str] = field(default_factory=list)
    passes_failed: list[str] = field(default_factory=list)
    passes_dependency_blocked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary(self) -> dict[str, Any]:
        return {
            "v2_pipeline_scheduler_used": self.v2_pipeline_scheduler_used,
            "pipeline_stage_count": self.pipeline_stage_count,
            "max_parallelism": self.max_parallelism,
            "max_sql_workers": self.max_sql_workers,
            "max_api_workers": self.max_api_workers,
            "parallel_groups": self.parallel_groups,
            "dependency_edges": self.dependency_edges,
            "stage_events": _summary_stage_events(self.stage_events),
            "passes_completed": self.passes_completed,
            "passes_failed": self.passes_failed,
            "passes_dependency_blocked": self.passes_dependency_blocked,
        }


class V2PipelineScheduler:
    """Resource-bounded stage scheduler for LLM-owned pass DAGs.

    The scheduler only orders LLM-declared passes through fixed runtime stages.
    It never changes pass semantics, SQL/API candidates, dependencies, or pass
    membership.
    """

    def __init__(
        self,
        *,
        max_parallelism: int = 4,
        max_sql_workers: int = 2,
        max_api_workers: int = 2,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.max_parallelism = max(1, int(max_parallelism))
        self.max_sql_workers = max(1, int(max_sql_workers))
        self.max_api_workers = max(1, int(max_api_workers))
        self.timeout_seconds = float(timeout_seconds)

    def schedule(self, passes: list[LLMUnifiedPass], graph_gate: PassGraphGateResult) -> V2PipelineSchedule:
        events: list[dict[str, Any]] = []
        histories: dict[str, list[dict[str, Any]]] = {item.pass_id: [] for item in passes}
        completed: list[str] = []
        failed: list[str] = []
        blocked: list[str] = []
        pass_by_id = {item.pass_id: item for item in passes}
        max_seen_parallel = 0
        max_seen_sql = 0
        max_seen_api = 0

        if not graph_gate.passed:
            failed = list(graph_gate.pass_ids)
            return V2PipelineSchedule(
                v2_pipeline_scheduler_used=bool(passes),
                pipeline_stage_count=len(PIPELINE_STAGES),
                max_parallelism=self.max_parallelism,
                max_sql_workers=self.max_sql_workers,
                max_api_workers=self.max_api_workers,
                max_observed_parallelism=0,
                max_observed_sql_workers=0,
                max_observed_api_workers=0,
                parallel_groups=graph_gate.parallel_groups,
                dependency_edges=graph_gate.dependency_edges,
                stage_events=[],
                pass_stage_history=histories,
                passes_completed=[],
                passes_failed=failed,
                passes_dependency_blocked=blocked,
            )

        for group in graph_gate.parallel_groups:
            group_passes = [pass_by_id[pass_id] for pass_id in group if pass_id in pass_by_id]
            for batch in _chunks(group_passes, self.max_parallelism):
                max_seen_parallel = max(max_seen_parallel, len(batch))
                _record_stage(events, histories, batch, "PLAN_READY")
                _record_stage(events, histories, batch, "DEPENDENCY_READY")
                _record_stage(events, histories, batch, "SQL_API_GATE")
                sql_count = sum(1 for item in batch if item.path in {"SQL", "SQL_AND_API"})
                api_count = sum(1 for item in batch if item.path in {"API", "SQL_AND_API"})
                max_seen_sql = max(max_seen_sql, min(sql_count, self.max_sql_workers))
                max_seen_api = max(max_seen_api, min(api_count, self.max_api_workers))
                _record_stage(events, histories, batch, "EXECUTE")
                _record_stage(events, histories, batch, "NORMALIZE_PASS_RESULT")
                _record_stage(events, histories, batch, "EVIDENCEBUS_APPEND")
                _record_stage(events, histories, batch, "RESULTBUNDLE_APPEND")
                _record_stage(events, histories, batch, "READY_FOR_FINAL_COMPOSITION")
                completed.extend(item.pass_id for item in batch)

        return V2PipelineSchedule(
            v2_pipeline_scheduler_used=bool(passes),
            pipeline_stage_count=len(PIPELINE_STAGES),
            max_parallelism=self.max_parallelism,
            max_sql_workers=self.max_sql_workers,
            max_api_workers=self.max_api_workers,
            max_observed_parallelism=max_seen_parallel,
            max_observed_sql_workers=max_seen_sql,
            max_observed_api_workers=max_seen_api,
            parallel_groups=graph_gate.parallel_groups,
            dependency_edges=graph_gate.dependency_edges,
            stage_events=events,
            pass_stage_history=histories,
            passes_completed=completed,
            passes_failed=failed,
            passes_dependency_blocked=blocked,
        )


def _record_stage(
    events: list[dict[str, Any]],
    histories: dict[str, list[dict[str, Any]]],
    passes: list[LLMUnifiedPass],
    stage: str,
) -> None:
    for item in passes:
        _event(events, histories, item.pass_id, stage, "started")
    for item in passes:
        _event(events, histories, item.pass_id, stage, "completed")


def _event(
    events: list[dict[str, Any]],
    histories: dict[str, list[dict[str, Any]]],
    pass_id: str,
    stage: str,
    event: str,
) -> None:
    payload = {
        "pass_id": pass_id,
        "stage": stage,
        "event": event,
        "timestamp": f"t{len(events) + 1:06d}",
    }
    events.append(payload)
    histories.setdefault(pass_id, []).append(payload)


def _chunks(values: list[LLMUnifiedPass], size: int) -> list[list[LLMUnifiedPass]]:
    return [values[index : index + size] for index in range(0, len(values), size)] or []


def _summary_stage_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gate_starts = [item for item in events if item.get("stage") == "SQL_API_GATE" and item.get("event") == "started"]
    final_ready = [item for item in events if item.get("stage") == "READY_FOR_FINAL_COMPOSITION" and item.get("event") == "completed"]
    important = gate_starts + final_ready
    seen = {id(item) for item in important}
    rest = [item for item in events if id(item) not in seen and item.get("stage") in {"SQL_API_GATE", "EXECUTE", "READY_FOR_FINAL_COMPOSITION"}]
    return important + rest if important else events
