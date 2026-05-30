from __future__ import annotations

from dashagent.llm_unified_planner import normalize_llm_unified_plan
from dashagent.pass_graph_gate import PassGraphGate


def test_pass_graph_gate_accepts_valid_dependency_graph():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "lookup",
                    "subtask": "Lookup campaign.",
                    "path": "SQL",
                    "can_run_parallel": False,
                    "depends_on": [],
                    "sql": {"query": "SELECT campaign_id FROM dim_campaign", "params": []},
                },
                {
                    "pass_id": "details",
                    "subtask": "Use campaign id.",
                    "path": "API",
                    "can_run_parallel": False,
                    "depends_on": ["lookup"],
                    "api_request": {"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {"id": "{{lookup.result.campaign_id}}"}},
                },
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is True
    assert result.dependency_edges == [["lookup", "details"]]
    assert result.parallel_groups == [["lookup"], ["details"]]


def test_pass_graph_gate_rejects_duplicate_pass_ids():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {"pass_id": "same", "path": "SQL", "sql": {"query": "SELECT 1", "params": []}},
                {"pass_id": "same", "path": "API", "api_request": {"method": "GET", "path": "/x", "params": {}}},
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "duplicate_pass_id"


def test_pass_graph_gate_rejects_unknown_dependency():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "details",
                    "path": "SQL",
                    "depends_on": ["missing"],
                    "sql": {"query": "SELECT 1", "params": []},
                }
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "unknown_dependency"


def test_pass_graph_gate_rejects_dependency_cycle():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {"pass_id": "a", "path": "SQL", "depends_on": ["b"], "sql": {"query": "SELECT 1", "params": []}},
                {"pass_id": "b", "path": "SQL", "depends_on": ["a"], "sql": {"query": "SELECT 1", "params": []}},
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "dependency_cycle"


def test_pass_graph_gate_rejects_path_field_mismatch():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "api_declared",
                    "path": "API",
                    "sql": {"query": "SELECT 1", "params": []},
                    "api_request": None,
                }
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "path_mismatch"
