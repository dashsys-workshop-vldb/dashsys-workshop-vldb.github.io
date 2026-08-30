from __future__ import annotations

import json

import dashagent.llm_client as llm_client
from dashagent.agent_tools import DEFAULT_AGENT_STRATEGY
from dashagent.llm_client import GeminiLLMClient, OpenAILLMClient, get_llm_client


def clear_llm_env(monkeypatch):
    for key in [
        "LLM_PROVIDER",
        "DASHAGENT_LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "PIONEER_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_TIMEOUT_SEC",
    ]:
        monkeypatch.delenv(key, raising=False)


class FakeGeminiResponse:
    text = "tool submitted"
    function_calls = []
    candidates = []
    usage_metadata = None

    def __init__(self, *, function_calls=None, text="tool submitted", finish_reason="STOP", usage=None):
        self.text = text
        self.function_calls = function_calls or []
        self.candidates = [type("Candidate", (), {"finish_reason": finish_reason, "content": {"role": "model"}})()]
        self.usage_metadata = usage or {"prompt_token_count": 5, "candidates_token_count": 7, "total_token_count": 12}


class FakeFunctionCall:
    def __init__(self, *, name, args):
        self.id = "gemini_call_1"
        self.name = name
        self.args = args


class FakeModels:
    def __init__(self, captured):
        self.captured = captured

    def generate_content(self, **payload):
        self.captured["payload"] = payload
        return FakeGeminiResponse(
            function_calls=[
                FakeFunctionCall(
                    name="submit_semantic_ir_plan",
                    args={"route": "DIRECT", "direct_answer": "A schema defines data structure.", "tasks": []},
                )
            ]
        )


class FakeGenAIClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        captured = kwargs.pop("_captured")
        captured["init"] = kwargs
        self.models = FakeModels(captured)


class FakeTypes:
    class FunctionDeclaration:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Tool:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


def test_gemini_client_normalizes_function_call(monkeypatch):
    captured = {}

    def fake_client_factory(**kwargs):
        kwargs["_captured"] = captured
        return FakeGenAIClient(**kwargs)

    clear_llm_env(monkeypatch)
    monkeypatch.setattr(llm_client, "GeminiSDKClient", fake_client_factory)
    monkeypatch.setattr(llm_client, "GeminiTypes", FakeTypes)
    client = GeminiLLMClient(api_key="unit-test-gemini-key", model="gemini-test", timeout_seconds=11)

    result = client.generate_messages(
        [
            {"role": "system", "content": "Use the tool."},
            {"role": "user", "content": "What is a schema?"},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "submit_semantic_ir_plan",
                    "description": "Submit Semantic IR.",
                    "parameters": {"type": "object", "properties": {"route": {"type": "string"}}},
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "submit_semantic_ir_plan"}},
        parallel_tool_calls=False,
    )

    assert result["ok"] is True
    assert result["provider"] == "gemini"
    assert result["model"] == "gemini-test"
    assert result["sdk_path_used"] is True
    assert result["backend_type"] == "gemini_sdk"
    assert result["tool_calls"][0]["name"] == "submit_semantic_ir_plan"
    assert result["tool_calls"][0]["arguments"]["route"] == "DIRECT"
    assert json.loads(result["tool_calls"][0]["raw_arguments"])["direct_answer"] == "A schema defines data structure."
    assert captured["init"]["api_key"] == "unit-test-gemini-key"
    assert captured["payload"]["model"] == "gemini-test"
    assert "unit-test-gemini-key" not in str(result)


def test_gemini_provider_selection_and_no_key_noop(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("DASHAGENT_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm_client, "GeminiSDKClient", object())
    monkeypatch.setattr(llm_client, "GeminiTypes", FakeTypes)

    client = get_llm_client()
    result = client.generate("system", "user")

    assert client.available() is False
    assert result["skipped"] is True
    assert result["reason"] == "GEMINI_API_KEY is not set"


def test_gemini_provider_selection_returns_client_when_configured(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("DASHAGENT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(llm_client, "GeminiSDKClient", object())
    monkeypatch.setattr(llm_client, "GeminiTypes", FakeTypes)

    client = get_llm_client()

    assert isinstance(client, GeminiLLMClient)
    assert client.available() is True
    assert client.provider_name() == "gemini"
    assert client.model_name() == "gemini-2.5-flash"


def test_openai_path_still_selects_openai(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("DASHAGENT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-openai-key")

    client = get_llm_client()

    assert isinstance(client, OpenAILLMClient)
    assert client.provider_name() == "openai"


def test_packaged_default_remains_sql_first_api_verify():
    assert DEFAULT_AGENT_STRATEGY == "SQL_FIRST_API_VERIFY"
