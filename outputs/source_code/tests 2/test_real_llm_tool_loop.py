from __future__ import annotations

import json

from dashagent.llm_tool_agent import run_real_llm_two_tools_baseline


class FakeLLMClient:
    def __init__(self, responses, provider="fake"):
        self.responses = list(responses)
        self.calls = []
        self.provider = provider

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return self.provider

    def model_name(self) -> str:
        return "fake-model"

    def generate_messages(self, messages, tools=None, tool_choice=None):
        self.calls.append({"messages": list(messages), "tools": tools, "tool_choice": tool_choice})
        if self.responses:
            return self.responses.pop(0)
        return {"ok": True, "content": "Done.", "tool_calls": [], "finish_reason": "stop"}

    def generate(self, system_prompt, user_prompt, tools=None):
        return self.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            tools=tools,
            tool_choice="auto" if tools else None,
        )


def test_real_llm_two_tools_baseline_skips_without_key(monkeypatch, tiny_project):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_real_llm_two_tools_baseline("List all journeys", config=tiny_project)
    assert result["skipped"] is True
    assert result["real_llm_used"] is False


def test_native_tool_call_executes_sql_and_finishes(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "tool": "execute_sql",
                        "arguments": {"sql": "SELECT COUNT(*) AS count FROM dim_campaign"},
                    }
                ],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"There are 2 campaigns."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("How many campaigns are there?", config=tiny_project, llm_client=client)
    assert result["real_llm_called"] is True
    assert result["tool_calls_executed"] is True
    assert result["valid_agent_run"] is True
    assert result["tool_call_count"] == 1
    assert result["llm_tool_calls"][0]["validation"]["ok"] is True
    assert result["llm_tool_calls"][0]["tool_name"] == "execute_sql"
    second_call_messages = client.calls[1]["messages"]
    assert any(message.get("role") == "assistant" and message.get("tool_calls") for message in second_call_messages)
    assert any(message.get("role") == "tool" and message.get("tool_call_id") == "call_1" for message in second_call_messages)


def test_json_tool_call_executes_sql(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"execute_sql","arguments":{"sql":"SELECT name FROM dim_campaign ORDER BY name"}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"Birthday Message and Welcome Journey."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("List all journeys", config=tiny_project, llm_client=client)
    assert result["tool_calls_executed"] is True
    assert result["valid_agent_run"] is True


def test_invalid_first_response_retries_then_succeeds(tiny_project):
    client = FakeLLMClient(
        [
            {"ok": True, "content": "I should query the database.", "tool_calls": []},
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"execute_sql","arguments":{"sql":"SELECT COUNT(*) AS count FROM dim_campaign"}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"There are 2 campaigns."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("How many campaigns are there?", config=tiny_project, llm_client=client)
    assert result["valid_agent_run"] is True
    assert len(client.calls) >= 3
    assert client.calls[1]["tool_choice"] == {"type": "function", "function": {"name": "execute_sql"}}


def test_invalid_after_retry_is_failed_baseline(tiny_project):
    client = FakeLLMClient(
        [
            {"ok": True, "content": "not json", "tool_calls": []},
            {"ok": True, "content": "still not json", "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("List all journeys", config=tiny_project, llm_client=client)
    assert result["real_llm_called"] is True
    assert result["tool_calls_executed"] is False
    assert result["valid_agent_run"] is False
    assert result["skipped_or_failed"] is True
    assert result["failure_reason"] == "no_valid_tool_call_after_native_retry"


def test_openrouter_no_tool_calls_reports_model_limitation(tiny_project):
    client = FakeLLMClient(
        [
            {"ok": True, "content": "I can answer directly.", "tool_calls": []},
            {"ok": True, "content": "Still no tool call.", "tool_calls": []},
        ],
        provider="openrouter",
    )
    result = run_real_llm_two_tools_baseline("List all journeys", config=tiny_project, llm_client=client)
    assert result["valid_agent_run"] is False
    assert result["tool_calls_executed"] is False
    assert result["failure_reason"] == "model_did_not_return_tool_calls"


def test_destructive_sql_is_blocked_and_not_successful(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"execute_sql","arguments":{"sql":"DELETE FROM dim_campaign"}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"Deleted rows."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("Delete campaigns", config=tiny_project, llm_client=client)
    assert result["llm_tool_calls"][0]["validation"]["ok"] is False
    assert result["llm_tool_calls"][0]["executed"] is False
    assert result["valid_agent_run"] is False
    assert result["failure_reason"] == "no_valid_tool_calls_executed"


def test_max_tool_calls_enforced(tiny_project):
    calls = [
        {"tool": "execute_sql", "arguments": {"sql": "SELECT COUNT(*) AS count FROM dim_campaign"}}
        for _ in range(5)
    ]
    client = FakeLLMClient(
        [
            {"ok": True, "content": '{"tool_calls":' + json.dumps(calls) + ',"final_answer":null}', "tool_calls": []},
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"Done."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("How many campaigns are there?", config=tiny_project, llm_client=client, max_tool_calls=2)
    assert len(result["llm_tool_calls"]) == 2
