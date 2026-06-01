from __future__ import annotations

import json

from dashagent.llm_final_answer_composer import compose_llm_final_answer
from dashagent.llm_unified_planner import run_llm_unified_planner


class ToolCallClient:
    def __init__(self, tool_name: str, arguments: dict) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake_tool_provider"

    def model_name(self) -> str:
        return "fake_tool_model"

    def generate(self, system_prompt, user_prompt, tools=None):
        return self.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            tools=tools,
            tool_choice="required" if tools else None,
        )

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        self.calls.append({"tools": tools, "tool_choice": tool_choice, "messages": messages})
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": "",
            "tool_calls": [
                {
                    "name": self.tool_name,
                    "tool": self.tool_name,
                    "arguments": self.arguments,
                    "raw_arguments": json.dumps(self.arguments),
                }
            ],
        }


def test_llm_unified_planner_prefers_sdk_toolcall_structured_output(monkeypatch):
    client = ToolCallClient(
        "submit_v2_plan",
        {
            "route": "LLM_DIRECT",
            "evidence_order": "NO_EVIDENCE",
            "direct_answer": "A schema defines data structure.",
            "passes": [],
            "aggregation_instruction": None,
            "reason": "pure concept",
        },
    )
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)

    plan = run_llm_unified_planner(user_prompt="What is a schema?", schema_context={}, endpoint_context=[])

    assert plan.route == "LLM_DIRECT"
    assert plan.direct_answer == "A schema defines data structure."
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_v2_plan"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_v2_plan"


def test_llm_final_answer_composer_prefers_sdk_toolcall_structured_output(monkeypatch):
    client = ToolCallClient(
        "submit_final_answer",
        {
            "final_answer": "There are 2 campaigns.",
            "used_pass_ids": ["p1"],
            "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["p1"]}],
            "caveats_included": [],
            "unanswered_subtasks": [],
        },
    )
    monkeypatch.setattr("dashagent.llm_final_answer_composer.get_llm_client", lambda: client)

    candidate = compose_llm_final_answer(card={"task": "LLM_OWNED_FINAL_ANSWER_COMPOSITION"})

    assert candidate.final_answer == "There are 2 campaigns."
    assert candidate.used_pass_ids == ["p1"]
    assert client.calls[0]["tools"][0]["function"]["name"] == "submit_final_answer"
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_final_answer"
