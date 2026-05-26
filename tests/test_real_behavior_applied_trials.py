from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from dashagent.executor import AgentExecutor
from dashagent.checkpoints import CheckpointLogger
from dashagent.evidence_policy import API_REQUIRED, ApiNeedDecision
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


def _sql_then_optional_api_plan(query, routing, metadata, strategy, analysis=None):
    return Plan(
        strategy=strategy,
        rationale="unit SQL direct answer plus optional API",
        steps=[
            PlanStep(
                action="sql",
                purpose="unit SQL direct answer",
                sql="SELECT campaign_id AS id, name FROM dim_campaign ORDER BY campaign_id",
            ),
            PlanStep(
                action="api",
                purpose="unit optional schema API",
                method="GET",
                url="/data/foundation/schemaregistry/tenant/schemas",
                params={},
            ),
        ],
    )


def test_semantic_no_tool_applied_trial_skips_tools_for_conceptual_prompt(tiny_project):
    cfg = replace(
        tiny_project,
        enable_semantic_intent_classifier=True,
        enable_semantic_route_decision_ladder=True,
        semantic_route_shadow_only=False,
        enable_semantic_no_tool_applied_trial=True,
        real_behavior_trial_mode="semantic_no_tool_applied_real_trial",
    )
    executor = AgentExecutor(cfg)

    result = executor.run("What is a schema?", strategy="SQL_FIRST_API_VERIFY", query_id="semantic_no_tool_unit")

    assert result["tool_results"] == []
    assert result["plan"]["steps"] == []
    assert any(
        checkpoint.get("checkpoint_id") == "checkpoint_real_behavior_applied_trial"
        and checkpoint.get("output", {}).get("trial_mode") == "semantic_no_tool_applied_real_trial"
        and checkpoint.get("output", {}).get("applied") is True
        for checkpoint in result["checkpoints"]
    )


def test_post_sql_deterministic_applied_trial_drops_optional_api_after_direct_sql(tiny_project):
    cfg = replace(
        tiny_project,
        enable_post_sql_api_decision=True,
        post_sql_api_decision_shadow_only=False,
        enable_post_sql_deterministic_applied_trial=True,
        real_behavior_trial_mode="post_sql_deterministic_applied_real_trial",
    )
    client = CountingAPIClient()
    executor = AgentExecutor(cfg, api_client=client)
    executor.planner.create_plan = _sql_then_optional_api_plan

    result = executor.run("List campaigns", strategy="SQL_FIRST_API_VERIFY", query_id="post_sql_skip_unit")

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert client.calls == 0
    assert any(
        checkpoint.get("checkpoint_id") == "checkpoint_real_behavior_applied_trial"
        and checkpoint.get("output", {}).get("decision") == "SKIP_API"
        and checkpoint.get("output", {}).get("applied") is True
        for checkpoint in result["checkpoints"]
    )


def test_post_sql_deterministic_applied_trial_preserves_live_api_prompt(tiny_project):
    cfg = replace(
        tiny_project,
        enable_post_sql_api_decision=True,
        post_sql_api_decision_shadow_only=False,
        enable_post_sql_deterministic_applied_trial=True,
        real_behavior_trial_mode="post_sql_deterministic_applied_real_trial",
    )
    client = CountingAPIClient()
    executor = AgentExecutor(cfg, api_client=client)
    executor.planner.create_plan = _sql_then_optional_api_plan

    result = executor.run("List current Adobe schemas", strategy="SQL_FIRST_API_VERIFY", query_id="post_sql_keep_api_unit")

    assert [row["type"] for row in result["tool_results"]] == ["sql", "api"]
    assert client.calls == 1


def test_post_sql_api_required_uses_api_need_mode(tiny_project):
    cfg = replace(
        tiny_project,
        enable_post_sql_api_decision=True,
        enable_post_sql_deterministic_applied_trial=True,
        real_behavior_trial_mode="post_sql_deterministic_applied_real_trial",
    )
    executor = AgentExecutor(cfg)
    analysis = SimpleNamespace(
        answer_family="list",
        api_need_decision=ApiNeedDecision(API_REQUIRED, "unit required API", 1, ["schema_list"]),
    )
    tool_results = [
        {
            "type": "sql",
            "payload": {
                "ok": True,
                "row_count": 1,
                "rows": [{"id": "schema-1", "name": "Schema One"}],
            },
        }
    ]
    api_step = PlanStep(
        action="api",
        purpose="unit required API",
        method="GET",
        url="/data/foundation/schemaregistry/tenant/schemas",
        params={},
    )

    decision = executor._add_post_sql_api_decision_checkpoints(  # noqa: SLF001
        "List current Adobe schemas",
        analysis,
        tool_results,
        api_step,
        CheckpointLogger(),
    )

    assert decision is not None
    assert decision["api_required"] is True
    applied = executor._post_sql_api_applied_decision(decision)  # noqa: SLF001
    assert applied["applied"] is False
    assert "API_REQUIRED" in applied["blockers"]
