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


def test_raw_baseline_does_not_use_guided_features(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"call_api","arguments":{"method":"GET","url":"/data/core/ups/batch/abc/files","params":{}}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"No evidence."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("Which files are available for download in batch abc?", config=tiny_project, llm_client=client)
    first_user_payload = client.calls[0]["messages"][1]["content"]
    assert "schema_affordance" not in first_user_payload
    call = result["llm_tool_calls"][0]
    assert "endpoint_repair" not in call
    assert "guided_feedback" not in str(call)
    assert call["guided_features_used"] is False


def test_guided_baseline_repairs_endpoint(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"call_api","arguments":{"method":"GET","url":"/data/core/ups/batch/abc/files","params":{}}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"The API was dry-run only."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline(
        "Which files are available for download in batch abc?",
        config=tiny_project,
        llm_client=client,
        guided=True,
    )
    call = result["llm_tool_calls"][0]
    assert call["endpoint_repair"]["repaired"] is True
    assert call["repaired_url"] == "/data/foundation/export/batches/abc/files"
    assert result["repaired_endpoint_count"] == 1
    assert call["dry_run_only"] is True
    assert call["evidence_available"] is False


def test_guided_invalid_journey_table_suggests_dim_campaign(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"execute_sql","arguments":{"sql":"SELECT * FROM journey"}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"No evidence."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("List journeys", config=tiny_project, llm_client=client, guided=True)
    feedback = result["llm_tool_calls"][0]["result_preview"]["guided_feedback"]
    assert "dim_campaign" in feedback["closest_table_suggestions"]


def test_guided_information_schema_returns_schema_feedback(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": '{"tool_calls":[{"tool":"execute_sql","arguments":{"sql":"SELECT table_name FROM information_schema.tables"}}],"final_answer":null}',
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"No evidence."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("Show tables", config=tiny_project, llm_client=client, guided=True)
    preview = result["llm_tool_calls"][0]["result_preview"]
    assert preview["virtual_schema"] is True
    assert "allowed_tables" in preview
    assert "dim_campaign" in preview["allowed_tables"]


def test_uncertain_zero_row_rewrites_hard_negative(tiny_project):
    client = FakeLLMClient(
        [
            {
                "ok": True,
                "content": json.dumps(
                    {
                        "tool_calls": [
                            {
                                "tool": "execute_sql",
                                "arguments": {"sql": "SELECT * FROM dim_campaign WHERE name = 'Missing'"},
                            }
                        ],
                        "final_answer": None,
                    }
                ),
                "tool_calls": [],
            },
            {"ok": True, "content": '{"tool_calls":[],"final_answer":"Missing does not exist."}', "tool_calls": []},
        ]
    )
    result = run_real_llm_two_tools_baseline("Find journey 'Missing'", config=tiny_project, llm_client=client)
    assert "did not find evidence" in result["final_answer"]
