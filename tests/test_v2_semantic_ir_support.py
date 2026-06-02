from __future__ import annotations

import json

from dashagent.v2_semantic_ir import parse_semantic_ir_from_json_or_line_protocol
from dashagent.v2_semantic_ir_support import check_semantic_ir_support


def _schema_card() -> list[dict]:
    return [{"table": "dim_campaign", "columns": ["name", "status", "published_at"]}]


def _api_card() -> list[dict]:
    return [{"endpoint_id": "journeys", "method": "GET", "path": "/ajo/journey", "path_params": []}]


def _local_plan(operation: str = "LIST", **task_overrides) -> dict:
    task = {
        "task_id": "t1",
        "kind": "LOCAL_QUERY",
        "operation": operation,
        "source": "LOCAL_SNAPSHOT",
        "local_query": {
            "table": "dim_campaign",
            "fields": ["name", "status"],
            "filters": [{"field": "name", "op": "contains", "value": "Birthday"}],
            "limit": 10,
            "count": False,
        },
        "api_query": None,
        "depends_on": [],
        "description": "List local campaigns.",
        "required": True,
    }
    task.update(task_overrides)
    return {"route": "EVIDENCE", "direct_answer": None, "tasks": [task], "aggregation_instruction": "Answer from t1."}


def test_simple_list_count_contains_and_in_filters_are_supported():
    list_plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(_local_plan()))
    assert check_semantic_ir_support(list_plan, _schema_card(), _api_card()).supported is True

    count_payload = _local_plan("COUNT")
    count_payload["tasks"][0]["local_query"].update({"fields": [], "filters": [], "limit": None, "count": True})
    assert check_semantic_ir_support(parse_semantic_ir_from_json_or_line_protocol(json.dumps(count_payload)), _schema_card(), _api_card()).supported is True

    in_payload = _local_plan()
    in_payload["tasks"][0]["local_query"]["filters"] = [{"field": "status", "op": "in", "value": ["draft", "published"]}]
    assert check_semantic_ir_support(parse_semantic_ir_from_json_or_line_protocol(json.dumps(in_payload)), _schema_card(), _api_card()).supported is True


def test_unsupported_local_features_return_objective_reason_without_prompt_text():
    payload = _local_plan(
        "LIST",
        requires_raw_sql_fallback=True,
        raw_sql_reason="Needs grouping by status.",
        unsupported_features=["GROUP_BY", "JOIN"],
    )
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload))

    result = check_semantic_ir_support(plan, _schema_card(), _api_card())

    assert result.supported is False
    assert result.task_id == "t1"
    assert result.operation == "LIST"
    assert result.recommended_action == "RAW_SQL_FALLBACK"
    assert "GROUP_BY" in result.unsupported_features
    assert "JOIN" in result.unsupported_features
    assert "Needs grouping" in result.unsupported_reason


def test_unknown_operation_and_post_api_are_unsupported():
    class FakeTask:
        task_id = "bad_op"
        kind = "LOCAL_QUERY"
        operation = "PIVOT"
        source = "LOCAL_SNAPSHOT"
        local_query = object()
        api_query = None
        unsupported_features = []
        requires_raw_sql_fallback = False

    class FakePlan:
        route = "EVIDENCE"
        tasks = [FakeTask()]

    result = check_semantic_ir_support(FakePlan(), _schema_card(), _api_card())
    assert result.supported is False
    assert result.unsupported_features == ["UNKNOWN_OPERATION"]
    assert result.recommended_action == "LLM_REPAIR_IR"

    payload = _local_plan()
    payload["tasks"][0].update(
        {
            "kind": "LIVE_QUERY",
            "source": "LIVE_API",
            "local_query": None,
            "api_query": {"endpoint_id": "journeys", "method": "POST", "path_params": {}, "query_params": {}},
        }
    )
    plan = parse_semantic_ir_from_json_or_line_protocol(json.dumps(payload))
    result = check_semantic_ir_support(plan, _schema_card(), _api_card())
    assert result.supported is False
    assert result.unsupported_features == ["NON_GET_API_METHOD"]
    assert result.recommended_action == "FAIL_SAFE"
