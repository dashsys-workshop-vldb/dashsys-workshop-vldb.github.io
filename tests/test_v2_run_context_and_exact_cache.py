from __future__ import annotations

from dashagent.evidence_bus import EvidenceBus
from dashagent.exact_pass_cache import ExactPassCache
from dashagent.llm_unified_planner import normalize_llm_unified_plan
from dashagent.result_bundle import ResultBundle
from dashagent.v2_run_context import RunContext, create_run_context


def _plan(passes: list[dict]):
    return normalize_llm_unified_plan(
        {"route": "EVIDENCE_PIPELINE", "evidence_order": "MULTI_PASS", "passes": passes},
        provider="fake",
        model="fake",
    )


def _sql_pass(pass_id: str, sql: str, params: list | None = None):
    return {
        "pass_id": pass_id,
        "subtask": f"SQL pass {pass_id}.",
        "path": "SQL",
        "can_run_parallel": True,
        "depends_on": [],
        "sql": {"query": sql, "params": params or []},
    }


def test_run_context_creates_single_prompt_run_ids_and_budget():
    context = create_run_context("What schemas do I have?", prompt_id="prompt-a")

    assert context.run_id.startswith("run_")
    assert context.original_prompt == "What schemas do I have?"
    assert context.plan_version == 1
    assert context.status == "RUNNING"
    assert context.result_bundle_id == f"bundle_{context.run_id}"
    assert context.evidence_bus_id == f"evidence_{context.run_id}"
    assert context.budget.max_repair_attempts == 1
    assert context.to_dict()["budget"]["max_answer_repair_attempts"] == 1


def test_exact_pass_cache_is_scoped_to_current_run_and_returns_new_pass_result():
    plan = _plan([_sql_pass("p1", "SELECT 1"), _sql_pass("p2", "SELECT 1")])
    cache = ExactPassCache(run_id="run_a", db_snapshot_version="snapshot_1")
    result = {
        "run_id": "run_a",
        "pass_id": "p1",
        "attempt_id": 0,
        "plan_version": 1,
        "status": "SUCCESS",
        "source_results": [{"source": "SQL", "status": "SUCCESS"}],
        "facts": ["x:1"],
    }

    cache.store(plan.passes[0], source="sql", pass_result=result)
    hit = cache.lookup(plan.passes[1], source="sql", target_pass_id="p2")
    other_run_cache = ExactPassCache(run_id="run_b", db_snapshot_version="snapshot_1")

    assert hit is not None
    assert hit is not result
    assert hit["run_id"] == "run_a"
    assert hit["pass_id"] == "p2"
    assert hit["source_results"][0]["source"] == "EXACT_PASS_CACHE"
    assert hit["cache_hit"] is True
    assert hit["deduped_from_pass_id"] == "p1"
    assert other_run_cache.lookup(plan.passes[1], source="sql", target_pass_id="p2") is None


def test_exact_pass_cache_does_not_cache_api_error_or_compile_error():
    plan = _plan([_sql_pass("p1", "SELECT broken")])
    cache = ExactPassCache(run_id="run_a")

    cache.store(plan.passes[0], source="sql", pass_result={"run_id": "run_a", "pass_id": "p1", "status": "COMPILE_ERROR"})

    assert cache.lookup(plan.passes[0], source="sql", target_pass_id="p2") is None


def test_result_bundle_idempotent_append_rejects_stale_and_foreign_runs():
    context = create_run_context("Question")
    bundle = ResultBundle(run_id=context.run_id)
    first = {
        "run_id": context.run_id,
        "pass_id": "p1",
        "attempt_id": 1,
        "plan_version": 1,
        "status": "SUCCESS",
        "source_results": [],
    }
    duplicate = dict(first)
    stale = {**first, "attempt_id": 0}
    foreign = {**first, "run_id": "run_other", "pass_id": "p2"}

    assert bundle.append_pass_result(first)["appended"] is True
    assert bundle.append_pass_result(duplicate)["appended"] is False
    assert bundle.append_pass_result(stale)["error_type"] == "stale_attempt"
    assert bundle.append_pass_result(foreign)["error_type"] == "run_isolation_error"
    assert bundle.pass_results_count == 1


def test_evidence_bus_rejects_foreign_run_and_duplicate_commit():
    bus = EvidenceBus(run_id="run_a")
    result = {"run_id": "run_a", "pass_id": "p1", "attempt_id": 0, "status": "SUCCESS", "facts": ["x:1"], "source_results": []}
    foreign = {"run_id": "run_b", "pass_id": "p2", "attempt_id": 0, "status": "SUCCESS", "facts": ["x:2"], "source_results": []}

    assert bus.observe_pass_result(result)["appended"] is True
    assert bus.observe_pass_result(result)["appended"] is False
    assert bus.observe_pass_result(foreign)["error_type"] == "run_isolation_error"
    assert bus.compact()["pass_result_count"] == 1
