from __future__ import annotations

import inspect

import dashagent.llm_client as llm_client
from dashagent.llm_client import AnthropicLLMClient, NoOpLLMClient, OpenAILLMClient, OpenRouterLLMClient, get_llm_client


def clear_llm_env(monkeypatch):
    for key in [
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "ANTHROPIC_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_noop_llm_client_skips_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    client = NoOpLLMClient()
    result = client.generate("system", "user")
    assert not client.available()
    assert result["skipped"] is True
    assert result["reason"] == "OPENAI_API_KEY is not set"


def test_openai_client_unavailable_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    client = OpenAILLMClient()
    assert not client.available()
    assert client.provider_name() == "none"
    result = client.generate("system", "user")
    assert result["skipped"] is True


def test_openrouter_client_skips_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    client = OpenRouterLLMClient()
    assert not client.available()
    assert client.provider_name() == "none"
    result = client.generate("system", "user")
    assert result["skipped"] is True
    assert result["reason"] == "OPENROUTER_API_KEY is not set"


def test_provider_selection_openrouter_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    client = get_llm_client()
    assert not client.available()
    result = client.generate("system", "user")
    assert result["skipped"] is True
    assert result["reason"] == "OPENROUTER_API_KEY is not set"


def test_provider_selection_openai_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    client = get_llm_client()
    assert not client.available()
    result = client.generate("system", "user")
    assert result["reason"] == "OPENAI_API_KEY is not set"


def test_provider_selection_prefers_explicit_openai_compatible_base(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")

    client = get_llm_client()

    assert client.available()
    assert client.provider_name() == "openai"
    assert client.model_name() == "qwen2.5-32b-instruct"


def test_provider_selection_anthropic(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unit-test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")

    client = get_llm_client()

    assert client.available()
    assert client.provider_name() == "anthropic"
    assert client.model_name() == "claude-test"


def test_openai_generate_messages_normalizes_native_tool_calls(monkeypatch):
    class FakeCompletion:
        def model_dump(self):
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "execute_sql",
                                        "arguments": '{"sql":"SELECT 1"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"total_tokens": 10},
            }

    class FakeCompletions:
        def create(self, **payload):
            return FakeCompletion()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = OpenAILLMClient(api_key="unit-test-openai-key")
    result = client.generate_messages(
        [{"role": "user", "content": "How many?"}],
        tools=[{"type": "function", "function": {"name": "execute_sql", "parameters": {"type": "object"}}}],
        tool_choice="auto",
    )
    assert result["ok"] is True
    assert result["finish_reason"] == "tool_calls"
    assert result["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "tool": "execute_sql",
            "name": "execute_sql",
            "arguments": {"sql": "SELECT 1"},
            "raw_arguments": '{"sql":"SELECT 1"}',
        }
    ]
    assert result["transport"] == "openai_sdk"


def test_openai_client_uses_sdk_base_url_and_model(monkeypatch):
    captured = {}

    class FakeCompletion:
        def model_dump(self):
            return {
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 3},
            }

    class FakeCompletions:
        def create(self, **payload):
            captured["payload"] = payload
            return FakeCompletion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, *, api_key=None, base_url=None, timeout=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout
            self.chat = FakeChat()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")

    client = OpenAILLMClient(api_key="unit-test-openai-key")
    result = client.generate_messages([{"role": "user", "content": "hello"}])

    assert result["ok"] is True
    assert result["transport"] == "openai_sdk"
    assert result["model"] == "qwen2.5-32b-instruct"
    assert captured["base_url"] == "https://photos-hewlett-safely-friends.trycloudflare.com/v1"
    assert captured["payload"]["model"] == "qwen2.5-32b-instruct"
    assert "unit-test-openai-key" not in str(result)


def test_openai_client_normalizes_qwen_hermes_tool_calls_from_sdk(monkeypatch):
    class FakeCompletion:
        def model_dump(self):
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "chatcmpl-tool-123",
                                    "type": "function",
                                    "function": {
                                        "name": "execute_sql",
                                        "arguments": '{"sql": "SELECT COUNT(*) AS count FROM dim_blueprint"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"total_tokens": 22},
            }

    class FakeCompletions:
        def create(self, **payload):
            return FakeCompletion()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = OpenAILLMClient(api_key="unit-test-openai-key", model="qwen2.5-32b-instruct")

    result = client.generate_messages(
        [{"role": "user", "content": "count schemas"}],
        tools=[{"type": "function", "function": {"name": "execute_sql", "parameters": {"type": "object"}}}],
        tool_choice="auto",
    )

    assert result["finish_reason"] == "tool_calls"
    assert result["tool_calls"][0]["name"] == "execute_sql"
    assert result["tool_calls"][0]["arguments"]["sql"] == "SELECT COUNT(*) AS count FROM dim_blueprint"


def test_openrouter_generate_messages_uses_openrouter_endpoint(monkeypatch):
    captured = {}

    class FakeCompletion:
        def model_dump(self):
            return {
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 3},
            }

    class FakeCompletions:
        def create(self, **payload):
            captured["payload"] = payload
            return FakeCompletion()

    class FakeOpenAI:
        def __init__(self, *, api_key=None, base_url=None, timeout=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = OpenRouterLLMClient(api_key="unit-test-openrouter-key", model="openai/gpt-4o-mini")
    result = client.generate_messages([{"role": "user", "content": "hello"}])
    assert result["ok"] is True
    assert result["provider"] == "openrouter"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["payload"]["model"] == "openai/gpt-4o-mini"
    assert "unit-test-openrouter-key" not in str(result)


def test_openai_client_classifies_and_redacts_sdk_auth_error(monkeypatch):
    class FakeCompletions:
        def create(self, **payload):
            raise RuntimeError("401 Unauthorized: Bearer unit-test-secret")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = OpenAILLMClient(api_key="unit-test-secret")
    result = client.generate_messages([{"role": "user", "content": "hello"}])

    assert result["ok"] is False
    assert result["error_category"] == "auth_or_401"
    assert "unit-test-secret" not in str(result)
    assert "[REDACTED]" in result["error"]


def test_anthropic_client_normalizes_tool_use(monkeypatch):
    captured = {}

    class FakeMessage:
        def model_dump(self):
            return {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "execute_sql",
                        "input": {"sql": "SELECT 1"},
                    }
                ],
                "usage": {"input_tokens": 7, "output_tokens": 5},
            }

    class FakeMessages:
        def create(self, **payload):
            captured["payload"] = payload
            return FakeMessage()

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.messages = FakeMessages()

    monkeypatch.setattr("dashagent.llm_client.Anthropic", FakeAnthropic)
    client = AnthropicLLMClient(api_key="unit-test-anthropic-key", model="claude-test")

    result = client.generate_messages(
        [{"role": "user", "content": "count schemas"}],
        tools=[{"type": "function", "function": {"name": "execute_sql", "parameters": {"type": "object"}}}],
        tool_choice="auto",
    )

    assert result["ok"] is True
    assert result["transport"] == "anthropic_sdk"
    assert result["finish_reason"] == "tool_calls"
    assert result["tool_calls"][0]["name"] == "execute_sql"
    assert result["tool_calls"][0]["arguments"] == {"sql": "SELECT 1"}
    assert result["usage"]["total_tokens"] == 12
    assert captured["payload"]["tools"][0]["name"] == "execute_sql"


def test_llm_client_has_no_requests_chat_completion_runtime():
    source = inspect.getsource(llm_client)
    assert "requests.post" not in source
    assert "requests.request" not in source
    assert "/chat/completions" not in source
    assert "deprecated_requests_fallback" not in source
