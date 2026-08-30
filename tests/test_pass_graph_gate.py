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


def test_pass_graph_gate_rejects_unknown_placeholder_reference():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "details",
                    "path": "SQL",
                    "depends_on": [],
                    "sql": {"query": "SELECT ? AS id", "params": ["{{lookup.result.id}}"]},
                }
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "unknown_placeholder_dependency"


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


def test_pass_graph_gate_rejects_empty_evidence_pipeline_plan():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "SQL_FIRST",
            "passes": [],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "empty_evidence_plan"


def test_pass_graph_gate_rejects_evidence_pipeline_with_only_direct_pass():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "concept",
                    "path": "DIRECT",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "NO_EVIDENCE",
                }
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "missing_executable_evidence_pass"


def test_pass_graph_gate_rejects_evidence_pipeline_with_only_aggregation_pass():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "aggregate",
                    "path": "AGGREGATION_ONLY",
                    "can_run_parallel": False,
                    "depends_on": [],
                }
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is False
    assert result.error_type == "aggregation_without_dependencies"


def test_pass_graph_gate_accepts_evidence_pipeline_with_direct_and_sql_passes():
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "concept",
                    "path": "DIRECT",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "NO_EVIDENCE",
                },
                {
                    "pass_id": "data",
                    "path": "SQL",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "sql": {"query": "SELECT 1", "params": []},
                },
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is True


def test_pass_graph_gate_accepts_declared_cache_alias_with_executable_producer():
    contract = {
        "source": "LOCAL_SNAPSHOT",
        "object": "journey",
        "entity": "Birthday Message",
        "operation": "STATUS",
        "fields": ["NAME", "STATUS"],
        "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
        "scope": "local",
        "freshness": "same_run",
    }
    plan = normalize_llm_unified_plan(
        {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS",
            "passes": [
                {
                    "pass_id": "local_status",
                    "path": "SQL",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "sql": {"query": "SELECT name, status FROM dim_campaign", "params": []},
                    "semantic_cache_key": "local_status:Birthday Message",
                    "result_contract": contract,
                },
                {
                    "pass_id": "local_status_again",
                    "path": "CACHE_ALIAS",
                    "can_run_parallel": False,
                    "depends_on": ["local_status"],
                    "reuse_result_from": "local_status",
                    "semantic_cache_key": "local_status:Birthday Message",
                    "result_contract": contract,
                    "sql": None,
                    "api_request": None,
                },
            ],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is True
    assert result.dependency_edges == [["local_status", "local_status_again"]]


def test_pass_graph_gate_allows_llm_direct_without_passes():
    plan = normalize_llm_unified_plan(
        {
            "route": "LLM_DIRECT",
            "evidence_order": "NO_EVIDENCE",
            "passes": [],
        },
        provider="fake",
        model="fake",
    )

    result = PassGraphGate(max_passes=4).check(plan)

    assert result.passed is True
