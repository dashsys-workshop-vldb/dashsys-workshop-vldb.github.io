from __future__ import annotations

from dashagent.executor import _dependency_error_runtime_pass, _dependency_precheck
from dashagent.llm_unified_planner import normalize_llm_unified_plan
from dashagent.pass_graph_gate import PassGraphGate
from dashagent.v2_pipeline_scheduler import V2PipelineScheduler


def _plan(passes: list[dict]):
    return normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": passes,
            "aggregation_instruction": "Combine all pass results.",
        },
        provider="fake",
        model="fake",
    )


def test_scheduler_pipelines_independent_passes_through_gate_before_first_pass_finishes():
    plan = _plan(
        [
            {
                "pass_id": "p1",
                "subtask": "First SQL pass.",
                "path": "SQL",
                "can_run_parallel": True,
                "depends_on": [],
                "sql": {"query": "SELECT 1", "params": []},
            },
            {
                "pass_id": "p2",
                "subtask": "Second SQL pass.",
                "path": "SQL",
                "can_run_parallel": True,
                "depends_on": [],
                "sql": {"query": "SELECT 2", "params": []},
            },
        ]
    )
    graph = PassGraphGate().check(plan)

    schedule = V2PipelineScheduler(max_parallelism=2, max_sql_workers=1, max_api_workers=1).schedule(plan.passes, graph)

    events = schedule.stage_events
    p2_gate_started = _event_index(events, "p2", "SQL_API_GATE", "started")
    p1_final_ready = _event_index(events, "p1", "READY_FOR_FINAL_COMPOSITION", "completed")
    assert p2_gate_started < p1_final_ready
    assert schedule.v2_pipeline_scheduler_used is True
    assert schedule.pipeline_stage_count == 8
    assert schedule.passes_completed == ["p1", "p2"]


def test_scheduler_respects_sql_api_and_parallelism_limits():
    plan = _plan(
        [
            {
                "pass_id": "sql1",
                "subtask": "SQL one.",
                "path": "SQL",
                "can_run_parallel": True,
                "depends_on": [],
                "sql": {"query": "SELECT 1", "params": []},
            },
            {
                "pass_id": "sql2",
                "subtask": "SQL two.",
                "path": "SQL",
                "can_run_parallel": True,
                "depends_on": [],
                "sql": {"query": "SELECT 2", "params": []},
            },
            {
                "pass_id": "api1",
                "subtask": "API one.",
                "path": "API",
                "can_run_parallel": True,
                "depends_on": [],
                "api_request": {"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {}},
            },
        ]
    )
    graph = PassGraphGate().check(plan)

    schedule = V2PipelineScheduler(max_parallelism=2, max_sql_workers=1, max_api_workers=1).schedule(plan.passes, graph)

    assert schedule.max_parallelism == 2
    assert schedule.max_sql_workers == 1
    assert schedule.max_api_workers == 1
    assert schedule.max_observed_parallelism <= 2
    assert schedule.max_observed_sql_workers <= 1
    assert schedule.max_observed_api_workers <= 1


def test_scheduler_keeps_dependent_pass_waiting_until_dependency_ready():
    plan = _plan(
        [
            {
                "pass_id": "lookup",
                "subtask": "Lookup id.",
                "path": "SQL",
                "can_run_parallel": False,
                "depends_on": [],
                "sql": {"query": "SELECT 1 AS id", "params": []},
            },
            {
                "pass_id": "details",
                "subtask": "Use id.",
                "path": "SQL",
                "can_run_parallel": False,
                "depends_on": ["lookup"],
                "sql": {"query": "SELECT ? AS id", "params": ["{{lookup.result.id}}"]},
            },
        ]
    )
    graph = PassGraphGate().check(plan)

    schedule = V2PipelineScheduler(max_parallelism=2).schedule(plan.passes, graph)

    events = schedule.stage_events
    details_ready = _event_index(events, "details", "DEPENDENCY_READY", "completed")
    lookup_result_ready = _event_index(events, "lookup", "RESULTBUNDLE_APPEND", "completed")
    assert lookup_result_ready < details_ready


def test_dependency_precheck_marks_failed_dependency_terminal_without_repair():
    plan = _plan(
        [
            {
                "pass_id": "producer",
                "subtask": "Lookup producer.",
                "path": "API",
                "can_run_parallel": False,
                "depends_on": [],
                "api_request": {"method": "GET", "path": "/data/foundation/test", "params": {}},
            },
            {
                "pass_id": "consumer",
                "subtask": "Use producer result.",
                "path": "SQL",
                "can_run_parallel": False,
                "depends_on": ["producer"],
                "sql": {"query": "SELECT ? AS id", "params": ["{{producer.result.id}}"]},
            },
        ]
    )
    runtime_passes = [
        {
            "pass_id": "producer",
            "status": "API_ERROR",
            "source_results": [{"source": "API", "status": "API_ERROR", "error": "provider unavailable"}],
        }
    ]

    precheck = _dependency_precheck(plan.passes[1], runtime_passes, run_id="run_1")

    assert precheck["resolved"] is False
    assert precheck["terminal_dependency_failure"] is True
    assert precheck["dependency_failed_tasks"] == ["producer"]
    assert precheck["blocked_task_ids"] == ["consumer"]

    blocked = _dependency_error_runtime_pass(plan.passes[1], precheck)
    assert blocked["status"] == "DEPENDENCY_FAILED"
    assert blocked["source_results"][0]["status"] == "DEPENDENCY_FAILED"


def test_dependency_precheck_allows_failed_order_only_dependency_without_placeholder():
    plan = _plan(
        [
            {
                "pass_id": "concept",
                "subtask": "Explain a concept.",
                "path": "DIRECT",
                "can_run_parallel": True,
                "depends_on": [],
            },
            {
                "pass_id": "data",
                "subtask": "Fetch data after concept.",
                "path": "SQL",
                "can_run_parallel": False,
                "depends_on": ["concept"],
                "sql": {"query": "SELECT name FROM dim_campaign LIMIT 10", "params": []},
            },
        ]
    )
    runtime_passes = [
        {
            "pass_id": "concept",
            "status": "ERROR",
            "source_results": [{"source": "DIRECT", "status": "ERROR", "error": "unsafe_direct_task_answer"}],
        }
    ]

    precheck = _dependency_precheck(plan.passes[1], runtime_passes, run_id="run_1")

    assert precheck["resolved"] is True
    assert precheck["terminal_dependency_failure"] is False
    assert precheck["dependency_failed_tasks"] == []
    assert precheck["ignored_failed_order_only_dependencies"] == ["concept"]


def test_dependency_precheck_marks_missing_dependency_terminal_without_repair():
    plan = _plan(
        [
            {
                "pass_id": "consumer",
                "subtask": "Use missing producer result.",
                "path": "SQL",
                "can_run_parallel": False,
                "depends_on": ["missing_producer"],
                "sql": {"query": "SELECT ? AS id", "params": ["{{missing_producer.result.id}}"]},
            }
        ]
    )

    precheck = _dependency_precheck(plan.passes[0], [], run_id="run_1")

    assert precheck["resolved"] is False
    assert precheck["terminal_dependency_failure"] is True
    assert precheck["missing_dependency_ids"] == ["missing_producer"]
    assert precheck["blocked_task_ids"] == ["consumer"]


def _event_index(events: list[dict], pass_id: str, stage: str, event: str) -> int:
    for index, item in enumerate(events):
        if item["pass_id"] == pass_id and item["stage"] == stage and item["event"] == event:
            return index
    raise AssertionError(f"Missing event {pass_id} {stage} {event}")
