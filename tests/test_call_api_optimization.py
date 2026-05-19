from __future__ import annotations

import re

from dashagent.core_tool_policy import (
    api_tool_cache_key,
    compact_api_outcome,
    should_skip_optional_api_call,
)
from dashagent.executor import AgentExecutor
from dashagent.planner import Plan, PlanStep


class CountingAPIClient:
    dry_run = False

    def __init__(self) -> None:
        self.calls = 0

    def call_api(self, method, url, params=None, headers=None):
        self.calls += 1
        return {
            "ok": True,
            "dry_run": False,
            "status_code": 200,
            "parsed_evidence": {
                "evidence_state": "live_success",
                "usable_evidence": True,
                "items": [{"id": "synthetic"}],
            },
        }


def test_api_cache_key_is_stable_and_redacted():
    one = api_tool_cache_key("get", "/data/foundation/flowservice/runs", {"limit": 10, "sandbox": "synthetic"})
    two = api_tool_cache_key("GET", "/data/foundation/flowservice/runs", {"sandbox": "synthetic", "limit": 10})

    assert one == two
    assert one.startswith("api_")
    assert "synthetic" not in one
    assert re.fullmatch(r"api_[a-f0-9]{16}", one)


def test_optional_api_skip_requires_sql_complete_and_preserves_required_calls():
    assert should_skip_optional_api_call(
        api_policy="API_OPTIONAL",
        sql_answer_complete=True,
        live_success_count=0,
        route_mode="SQL_PLUS_API",
    ).skip is True
    assert should_skip_optional_api_call(
        api_policy="API_REQUIRED",
        sql_answer_complete=True,
        live_success_count=0,
        route_mode="SQL_PLUS_API",
    ).skip is False
    assert should_skip_optional_api_call(
        api_policy="API_OPTIONAL",
        sql_answer_complete=False,
        live_success_count=0,
        route_mode="SQL_PLUS_API",
    ).skip is False
    assert should_skip_optional_api_call(
        api_policy="API_OPTIONAL",
        sql_answer_complete=True,
        live_success_count=0,
        route_mode="API_ONLY",
    ).skip is False


def test_compact_api_outcome_preserves_state_without_raw_secret_values():
    payload = {
        "ok": False,
        "dry_run": True,
        "status_code": 401,
        "error": "Authorization: Bearer SHOULD_NOT_APPEAR request-id=abc123",
        "endpoint_family": "audiences",
        "parsed_evidence": {
            "evidence_state": "api_error",
            "error_category": "auth_error",
            "usable_evidence": False,
        },
    }

    compact = compact_api_outcome(payload)

    assert compact["ok"] is False
    assert compact["dry_run"] is True
    assert compact["evidence_state"] == "api_error"
    assert compact["error_category"] == "auth_error"
    assert compact["usable_evidence"] is False
    assert compact["endpoint_family"] == "audiences"
    assert "SHOULD_NOT_APPEAR" not in str(compact)
    assert "Bearer" not in str(compact)
    assert len(compact["caveat"]) <= 160


def test_executor_reuses_duplicate_api_attempt_within_one_query(tiny_project):
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)

    def duplicate_api_plan(query, routing, metadata, strategy, analysis=None):
        step = PlanStep(
            action="api",
            purpose="unit duplicate",
            method="GET",
            url="/ajo/journey",
            params={"limit": 50},
        )
        return Plan(strategy=strategy, rationale="unit duplicate API plan", steps=[step, step])

    executor.planner.create_plan = duplicate_api_plan
    result = executor.run(
        "List journeys from Adobe",
        strategy="DETERMINISTIC_ROUTER_SELECTED_METADATA",
        query_id="duplicate_api_unit",
    )

    assert client.calls == 1
    assert len(result["tool_results"]) == 2
    assert all(row["type"] == "api" for row in result["tool_results"])
