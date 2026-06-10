from __future__ import annotations

import time

from dashagent.llm_unified_planner import normalize_llm_unified_plan
from dashagent.pass_graph_gate import PassGraphGate
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from dashagent.v2_execution_optimizer import BudgetLimits, PassResultCache, V2ExecutionOptimizer
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


def _sql_pass(pass_id: str, sql: str, *, depends_on: list[str] | None = None, optional: bool = False) -> dict:
    return {
        "pass_id": pass_id,
        "subtask": "Optional fallback pass." if optional else f"SQL pass {pass_id}.",
        "path": "SQL",
        "can_run_parallel": not depends_on,
        "depends_on": depends_on or [],
        "optional": optional,
        "sql": {"query": sql, "params": []},
    }


def _api_pass(pass_id: str, path: str, *, params: dict | None = None) -> dict:
    return {
        "pass_id": pass_id,
        "subtask": f"API pass {pass_id}.",
        "path": "API",
        "can_run_parallel": True,
        "depends_on": [],
        "api_request": {"method": "GET", "path": path, "params": params or {}},
    }


def test_critical_path_priority_does_not_change_dependencies():
    plan = _plan(
        [
            _sql_pass("root", "SELECT 1"),
            _sql_pass("short", "SELECT 2", depends_on=["root"]),
            _api_pass("long", "/data/foundation/schemaregistry/tenant/schemas"),
        ]
    )
    graph = PassGraphGate().check(plan)

    prepared = V2ExecutionOptimizer().prepare(plan.passes, graph)

    assert graph.dependency_edges == [["root", "short"]]
    assert prepared.dependency_edges == graph.dependency_edges
    assert set(prepared.pass_ids) == {"root", "short", "long"}
    assert prepared.backend_semantic_planning_used is False
    assert "long" in prepared.critical_path


def test_stage_level_pipeline_allows_second_pass_to_enter_gate_while_first_executes():
    plan = _plan([_sql_pass("p1", "SELECT 1"), _sql_pass("p2", "SELECT 2")])
    graph = PassGraphGate().check(plan)
    prepared = V2ExecutionOptimizer().prepare(plan.passes, graph)

    schedule = V2PipelineScheduler(max_parallelism=2).schedule(plan.passes, graph, parallel_groups=prepared.parallel_groups)

    p2_gate_started = _event_index(schedule.stage_events, "p2", "SQL_API_GATE", "started")
    p1_final_ready = _event_index(schedule.stage_events, "p1", "READY_FOR_FINAL_COMPOSITION", "completed")
    assert p2_gate_started < p1_final_ready


def test_cache_hit_reuses_identical_sql_pass_result_without_rewriting_sql():
    plan = _plan([_sql_pass("p1", "SELECT 1")])
    cache = PassResultCache()
    result = {"type": "sql", "pass_id": "p1", "payload": {"ok": True, "rows": [{"x": 1}], "sql": "SELECT 1"}}
    cache.store(plan.passes[0], "sql", result)

    cached = cache.lookup(plan.passes[0], "sql", target_pass_id="p2")

    assert cached is not None
    assert cached["cached"] is True
    assert cached["pass_id"] == "p2"
    assert cached["payload"]["sql"] == "SELECT 1"


def test_cache_hit_reuses_identical_api_pass_result_within_ttl():
    plan = _plan([_api_pass("p1", "/data/foundation/schemaregistry/tenant/schemas", params={"limit": 1})])
    cache = PassResultCache(api_ttl_seconds=60)
    result = {"type": "api", "pass_id": "p1", "payload": {"ok": True, "parsed_evidence": {"evidence_state": "live_success"}}}
    cache.store(plan.passes[0], "api", result, now=time.time())

    cached = cache.lookup(plan.passes[0], "api", target_pass_id="p2", now=time.time() + 1)

    assert cached is not None
    assert cached["cached"] is True
    assert cached["pass_id"] == "p2"


def test_duplicate_exact_pass_is_deduped_but_similar_pass_is_not():
    plan = _plan(
        [
            _sql_pass("first", "SELECT id FROM journeys"),
            _sql_pass("duplicate", "SELECT id FROM journeys"),
            _sql_pass("similar", "SELECT name FROM journeys"),
        ]
    )

    prepared = V2ExecutionOptimizer().prepare(plan.passes, PassGraphGate().check(plan))

    assert prepared.deduped_passes == [{"pass_id": "duplicate", "deduped_from": "first", "source": "sql"}]
    assert "similar" not in {item["pass_id"] for item in prepared.deduped_passes}


def test_optional_fallback_pass_is_early_stopped_when_required_evidence_exists():
    plan = _plan([_sql_pass("required", "SELECT 1"), _sql_pass("fallback", "SELECT 2", optional=True)])
    runtime_passes = [{"pass_id": "required", "status": "SUCCESS", "facts": ["count:1"]}]

    stop = V2ExecutionOptimizer().early_stop_decision(plan.passes[1], runtime_passes)

    assert stop["skip"] is True
    assert stop["reason"] == "optional_or_fallback_pass_skipped_after_required_evidence"


def test_required_pass_is_not_early_stopped():
    plan = _plan([_sql_pass("required", "SELECT 1")])

    stop = V2ExecutionOptimizer().early_stop_decision(plan.passes[0], [{"pass_id": "other", "status": "SUCCESS"}])

    assert stop["skip"] is False


def test_budget_limit_blocks_excessive_passes_safely():
    plan = _plan([_sql_pass("p1", "SELECT 1"), _sql_pass("p2", "SELECT 2")])

    prepared = V2ExecutionOptimizer(budget_limits=BudgetLimits(max_passes=1)).prepare(plan.passes, PassGraphGate(max_passes=4).check(plan))

    assert prepared.budget_exceeded is True
    assert prepared.budget_error == "max_passes_exceeded"
    assert prepared.backend_semantic_planning_used is False


def test_checkpoint_resume_skips_completed_pass_work():
    plan = _plan([_sql_pass("p1", "SELECT 1")])
    cache = PassResultCache()
    result = {"type": "sql", "pass_id": "p1", "payload": {"ok": True, "rows": [{"x": 1}], "sql": "SELECT 1"}}
    cache.store(plan.passes[0], "sql", result, checkpoint=True)

    optimizer = V2ExecutionOptimizer(pass_cache=cache)
    cached = optimizer.lookup_cached_result(plan.passes[0], "sql", target_pass_id="p1")

    assert cached is not None
    assert cached["checkpoint_resume"] is True
    assert optimizer.trace["checkpoint_resume_used"] is True


def test_model_cascade_triggers_only_on_malformed_planner_output():
    plan = _plan([_sql_pass("p1", "SELECT 1")])
    valid_graph = PassGraphGate().check(plan)
    malformed = normalize_llm_unified_plan({"route": "BROKEN"}, provider="fake", model="small")

    optimizer = V2ExecutionOptimizer()

    assert optimizer.should_cascade_planner(malformed, valid_graph) is True
    assert optimizer.should_cascade_planner(plan, valid_graph) is False


def test_optimizer_never_rewrites_sql_api_or_adds_semantic_passes():
    plan = _plan(
        [
            _sql_pass("p1", "SELECT * FROM journeys"),
            _api_pass("p2", "/data/foundation/schemaregistry/tenant/schemas"),
        ]
    )
    before = [item.to_dict() for item in plan.passes]

    prepared = V2ExecutionOptimizer().prepare(plan.passes, PassGraphGate().check(plan))
    after = [item.to_dict() for item in plan.passes]

    assert before == after
    assert prepared.pass_ids == ["p1", "p2"]
    assert prepared.backend_semantic_planning_used is False


def test_packaged_default_and_pioneer_model_major_contract_remain_unchanged():
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    prepared = V2ExecutionOptimizer().trace
    assert prepared["backend_semantic_planning_used"] is False
    assert prepared["model_major_sweep_semantics_changed"] is False


def _event_index(events: list[dict], pass_id: str, stage: str, event: str) -> int:
    for index, item in enumerate(events):
        if item["pass_id"] == pass_id and item["stage"] == stage and item["event"] == event:
            return index
    raise AssertionError(f"Missing event {pass_id} {stage} {event}")
