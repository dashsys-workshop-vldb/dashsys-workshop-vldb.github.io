from __future__ import annotations

import copy

from dashagent.llm_unified_planner import normalize_llm_unified_plan
from dashagent.v2_semantic_alias import materialize_semantic_alias_pass, validate_unified_plan_semantic_aliases


def _contract(**overrides):
    payload = {
        "source": "LOCAL_SNAPSHOT",
        "object": "journey",
        "entity": "Birthday Message",
        "operation": "STATUS",
        "fields": ["STATUS", "NAME"],
        "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
        "scope": "local",
        "freshness": "same_run",
    }
    payload.update(overrides)
    return payload


def _producer_pass(**overrides):
    payload = {
        "pass_id": "local_status",
        "subtask": "Get local status.",
        "path": "SQL",
        "can_run_parallel": True,
        "depends_on": [],
        "sql": {"query": 'SELECT "NAME", "STATUS" FROM "dim_campaign" WHERE "NAME" = ?', "params": ["Birthday Message"]},
        "semantic_cache_key": "local_status:Birthday Message",
        "result_contract": _contract(),
    }
    payload.update(overrides)
    return payload


def _alias_pass(**overrides):
    payload = {
        "pass_id": "local_status_again",
        "subtask": "Reuse local status.",
        "path": "CACHE_ALIAS",
        "can_run_parallel": False,
        "depends_on": ["local_status"],
        "sql": None,
        "api_request": None,
        "reuse_result_from": "local_status",
        "semantic_cache_key": "local_status:Birthday Message",
        "result_contract": _contract(fields=["NAME", "STATUS"]),
    }
    payload.update(overrides)
    return payload


def _plan(passes: list[dict]):
    return normalize_llm_unified_plan(
        {"route": "EVIDENCE_PIPELINE", "evidence_order": "MULTI_PASS", "passes": passes},
        provider="fake",
        model="fake",
    )


def test_valid_alias_passes_with_canonical_field_and_filter_order():
    producer = _producer_pass(result_contract=_contract(fields=["STATUS", "NAME"]))
    alias = _alias_pass(result_contract=_contract(fields=["NAME", "STATUS"]))

    result = validate_unified_plan_semantic_aliases(_plan([producer, alias]))

    assert result.passed is True
    assert result.semantic_alias_count == 1
    assert result.error_type is None


def test_alias_requires_declared_producer_and_dependency_edge():
    missing_source = _alias_pass(reuse_result_from="")
    result = validate_unified_plan_semantic_aliases(_plan([_producer_pass(), missing_source]))
    assert result.passed is False
    assert result.error_type == "invalid_semantic_alias"
    assert result.task_id == "local_status_again"

    missing_dep = _alias_pass(depends_on=[])
    result = validate_unified_plan_semantic_aliases(_plan([_producer_pass(), missing_dep]))
    assert result.passed is False
    assert "depends_on" in result.message


def test_alias_rejects_unknown_self_cycle_and_sql_or_api_payload():
    unknown = _alias_pass(reuse_result_from="missing", depends_on=["missing"])
    assert validate_unified_plan_semantic_aliases(_plan([_producer_pass(), unknown])).passed is False

    self_alias = _alias_pass(reuse_result_from="local_status_again", depends_on=["local_status_again"])
    assert validate_unified_plan_semantic_aliases(_plan([_producer_pass(), self_alias])).passed is False

    with_sql = _alias_pass(sql={"query": "SELECT 1", "params": []})
    result = validate_unified_plan_semantic_aliases(_plan([_producer_pass(), with_sql]))
    assert result.passed is False
    assert "must not contain sql" in result.message


def test_alias_rejects_cross_source_scope_operation_fields_filters_and_key():
    cases = [
        _alias_pass(result_contract=_contract(source="LIVE_API")),
        _alias_pass(result_contract=_contract(scope="live")),
        _alias_pass(result_contract=_contract(operation="DATE")),
        _alias_pass(result_contract=_contract(fields=["NAME", "PUBLISHEDAT"])),
        _alias_pass(result_contract=_contract(filters=[{"field": "STATUS", "op": "=", "value": "active"}])),
        _alias_pass(semantic_cache_key="different"),
    ]

    for alias in cases:
        result = validate_unified_plan_semantic_aliases(_plan([_producer_pass(), alias]))
        assert result.passed is False
        assert result.error_type == "invalid_semantic_alias"


def test_alias_to_alias_resolves_transitively_when_contracts_match():
    first_alias = _alias_pass()
    second_alias = _alias_pass(
        pass_id="local_status_third",
        depends_on=["local_status_again"],
        reuse_result_from="local_status_again",
    )

    result = validate_unified_plan_semantic_aliases(_plan([_producer_pass(), first_alias, second_alias]))

    assert result.passed is True
    assert result.semantic_alias_count == 2


def test_materialize_semantic_alias_success_creates_separate_pass_result_without_tool_call():
    plan = _plan([_producer_pass(), _alias_pass()])
    alias = plan.passes[1]
    producer_result = {
        "run_id": "run_alias",
        "pass_id": "local_status",
        "global_pass_id": "run_alias:local_status",
        "attempt_id": 0,
        "plan_version": 1,
        "subtask": "Get local status.",
        "path": "SQL",
        "status": "SUCCESS",
        "scope": "LOCAL_SNAPSHOT",
        "facts": ["name: Birthday Message", "status: active"],
        "caveats": [],
        "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"NAME": "Birthday Message", "STATUS": "active"}]}}],
    }

    alias_result = materialize_semantic_alias_pass(alias, [producer_result], run_id="run_alias", plan_version=1)

    assert alias_result is not producer_result
    assert alias_result["pass_id"] == "local_status_again"
    assert alias_result["path"] == "CACHE_ALIAS"
    assert alias_result["status"] == "SUCCESS"
    assert alias_result["source_results"][0]["source"] == "SEMANTIC_CACHE_ALIAS"
    assert alias_result["source_results"][0]["status"] == "SUCCESS"
    assert alias_result["facts"] == producer_result["facts"]
    assert alias_result["alias_materialized"] is True
    assert alias_result["reuse_result_from"] == "local_status"
    assert alias_result["shared_execution_id"] == "run_alias:local_status"
    assert alias_result["source_results"][0]["result"]["producer_pass_id"] == "local_status"

    alias_result["facts"].append("extra")
    assert producer_result["facts"] == ["name: Birthday Message", "status: active"]


def test_materialize_semantic_alias_marks_failed_source_without_copying_success():
    alias = _plan([_producer_pass(), _alias_pass()]).passes[1]
    failed_producer = {
        "run_id": "run_alias",
        "pass_id": "local_status",
        "status": "API_ERROR",
        "facts": [],
        "caveats": ["Live API unavailable."],
        "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API"}],
    }

    alias_result = materialize_semantic_alias_pass(alias, [copy.deepcopy(failed_producer)], run_id="run_alias", plan_version=1)

    assert alias_result["status"] == "ALIAS_SOURCE_FAILED"
    assert alias_result["alias_materialized"] is False
    assert alias_result["facts"] == []
    assert alias_result["source_results"][0]["source"] == "SEMANTIC_CACHE_ALIAS"
    assert alias_result["source_results"][0]["status"] == "ALIAS_SOURCE_FAILED"
    assert "local_status" in alias_result["caveats"][0]
