from __future__ import annotations

from dashagent.llm_unified_planner import normalize_llm_unified_plan


def test_normalize_multi_pass_plan_keeps_llm_declared_passes_and_aggregation_instruction():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "local_status",
                    "subtask": "Fetch local journey status.",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "SQL_FIRST",
                    "sql": {"query": "SELECT name, status FROM dim_campaign", "params": []},
                    "api_request": None,
                    "expected_result": "local status",
                },
                {
                    "pass_id": "live_status",
                    "subtask": "Fetch live journey status.",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "API_FIRST",
                    "sql": None,
                    "api_request": {"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {}},
                    "expected_result": "live status",
                },
            ],
            "aggregation_instruction": "Compare local and live status.",
            "reason": "two independent evidence needs",
        },
        provider="fake",
        model="fake-model",
    )

    assert plan.evidence_order == "MULTI_PASS"
    assert len(plan.passes) == 2
    assert plan.passes[0].pass_id == "local_status"
    assert plan.passes[0].sql is not None
    assert plan.passes[1].api_request is not None
    assert plan.aggregation_instruction == "Compare local and live status."
    payload = plan.to_dict()
    assert payload["passes"][0]["pass_id"] == "local_status"
    assert payload["passes"][1]["pass_id"] == "live_status"


def test_normalize_single_pass_plan_backfills_passes_for_backward_compatibility():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "SQL_FIRST",
            "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
            "api_request": None,
            "reason": "simple count",
        },
        provider="fake",
        model="fake-model",
    )

    assert len(plan.passes) == 1
    assert plan.passes[0].pass_id == "pass_1"
    assert plan.passes[0].sql is not None
    assert plan.sql is not None


def test_normalize_pure_direct_plan_has_zero_passes():
    plan = normalize_llm_unified_plan(
        {
            "route": "LLM_DIRECT",
            "evidence_order": "NO_EVIDENCE",
            "direct_answer": "A schema defines data structure.",
            "passes": [{"pass_id": "should_drop", "sql": {"query": "SELECT 1"}}],
            "reason": "concept",
        },
        provider="fake",
        model="fake-model",
    )

    assert plan.route == "LLM_DIRECT"
    assert plan.evidence_order == "NO_EVIDENCE"
    assert plan.passes == []
