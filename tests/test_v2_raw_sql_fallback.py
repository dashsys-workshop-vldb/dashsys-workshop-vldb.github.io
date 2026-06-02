from __future__ import annotations

import json

from dashagent.raw_sql_safety_gate import RawSQLSafetyGate
from dashagent.v2_raw_sql_fallback import (
    RAW_SQL_FALLBACK_TOOL_NAME,
    extract_raw_sql_fallback_tool_arguments,
    raw_sql_fallback_tool_schema,
    run_raw_sql_fallback_planner,
)
from dashagent.v2_semantic_ir_support import IRSupportResult


class RawSQLFallbackClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice, "parallel_tool_calls": parallel_tool_calls, **kwargs})
        payload = self.responses.pop(0)
        return {
            "ok": True,
            "provider": "fake",
            "model": "fake",
            "content": "",
            "tool_calls": [{"name": RAW_SQL_FALLBACK_TOOL_NAME, "arguments": payload}],
        }


def test_raw_sql_fallback_tool_parses_arguments():
    schema = raw_sql_fallback_tool_schema()
    assert schema["function"]["name"] == RAW_SQL_FALLBACK_TOOL_NAME

    args = extract_raw_sql_fallback_tool_arguments(
        {"tool_calls": [{"name": RAW_SQL_FALLBACK_TOOL_NAME, "arguments": {"task_id": "t1", "reason": "grouping", "sql": "SELECT COUNT(*) FROM t", "params": []}}]}
    )

    assert args["task_id"] == "t1"
    assert args["sql"].startswith("SELECT")


def test_raw_sql_fallback_planner_uses_model_sql_and_not_backend_sql():
    client = RawSQLFallbackClient([{"task_id": "t1", "reason": "Needs grouping.", "sql": "SELECT status, COUNT(*) AS count FROM dim_campaign GROUP BY status LIMIT 10", "params": []}])
    support = IRSupportResult(
        supported=False,
        unsupported_reason="GROUP_BY is outside Semantic IR v1.",
        unsupported_features=["GROUP_BY"],
        task_id="t1",
        operation="LIST",
        recommended_action="RAW_SQL_FALLBACK",
    )

    result = run_raw_sql_fallback_planner(
        client=client,
        user_prompt="Count campaigns by status.",
        semantic_plan={"tasks": [{"task_id": "t1", "source": "LOCAL_SNAPSHOT"}]},
        support_result=support,
        allowed_schema_card=[{"table": "dim_campaign", "columns": ["status"]}],
        safety_gate=RawSQLSafetyGate(),
    )

    assert result.ok is True
    assert result.sql == "SELECT status, COUNT(*) AS count FROM dim_campaign GROUP BY status LIMIT 10"
    assert result.backend_generated_sql is False
    assert result.safety_gate.passed is True
    assert client.calls[0]["tools"][0]["function"]["name"] == RAW_SQL_FALLBACK_TOOL_NAME
    assert "allowed_schema_card" in client.calls[0]["messages"][1]["content"]


def test_raw_sql_fallback_repairs_safety_failure_once():
    client = RawSQLFallbackClient(
        [
            {"task_id": "t1", "reason": "Need raw SQL.", "sql": "SELECT name FROM dim_campaign", "params": []},
            {"task_id": "t1", "reason": "Add required limit.", "sql": "SELECT name FROM dim_campaign LIMIT 10", "params": []},
        ]
    )
    support = IRSupportResult(False, "unsupported", ["GROUP_BY"], "t1", "LIST", "RAW_SQL_FALLBACK")

    result = run_raw_sql_fallback_planner(
        client=client,
        user_prompt="List campaigns.",
        semantic_plan={"tasks": [{"task_id": "t1", "source": "LOCAL_SNAPSHOT"}]},
        support_result=support,
        allowed_schema_card=[{"table": "dim_campaign", "columns": ["name"]}],
        safety_gate=RawSQLSafetyGate(),
    )

    assert result.ok is True
    assert result.sql.endswith("LIMIT 10")
    assert result.repair_attempted is True
    assert result.repair_success is True
    assert len(client.calls) == 2


def test_raw_sql_fallback_not_allowed_for_api_task():
    client = RawSQLFallbackClient([{"task_id": "api_task", "reason": "bad", "sql": "SELECT 1", "params": []}])
    support = IRSupportResult(False, "API unsupported", ["LIVE_API"], "api_task", "LIST", "RAW_SQL_FALLBACK")

    result = run_raw_sql_fallback_planner(
        client=client,
        user_prompt="Show live schemas.",
        semantic_plan={"tasks": [{"task_id": "api_task", "source": "LIVE_API"}]},
        support_result=support,
        allowed_schema_card=[],
        safety_gate=RawSQLSafetyGate(),
    )

    assert result.ok is False
    assert result.rejected_reason == "raw_sql_fallback_requires_local_snapshot_task"
    assert client.calls == []
