from __future__ import annotations

from dashagent.llm_client import NoOpLLMClient, OpenAILLMClient, OpenRouterLLMClient, get_llm_client


def test_noop_llm_client_skips_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = NoOpLLMClient()
    result = client.generate("system", "user")
    assert not client.available()
    assert result["skipped"] is True
    assert result["reason"] == "OPENAI_API_KEY is not set"


def test_openai_client_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = OpenAILLMClient()
    assert not client.available()
    assert client.provider_name() == "none"
    result = client.generate("system", "user")
    assert result["skipped"] is True


def test_openrouter_client_skips_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = OpenRouterLLMClient()
    assert not client.available()
    assert client.provider_name() == "none"
    result = client.generate("system", "user")
    assert result["skipped"] is True
    assert result["reason"] == "OPENROUTER_API_KEY is not set"


def test_provider_selection_openrouter_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = get_llm_client()
    assert not client.available()
    result = client.generate("system", "user")
    assert result["skipped"] is True
    assert result["reason"] == "OPENROUTER_API_KEY is not set"


def test_provider_selection_openai_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = get_llm_client()
    assert not client.available()
    result = client.generate("system", "user")
    assert result["reason"] == "OPENAI_API_KEY is not set"


def test_provider_selection_prefers_explicit_openai_compatible_base(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://photos-hewlett-safely-friends.trycloudflare.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5-32b-instruct")

    client = get_llm_client()

    assert client.available()
    assert client.provider_name() == "openai"
    assert client.model_name() == "qwen2.5-32b-instruct"


def test_openai_generate_messages_normalizes_native_tool_calls(monkeypatch):
    monkeypatch.setenv("OPENAI_USE_REQUESTS_FALLBACK", "1")

    class FakeResponse:
        ok = True

        def json(self):
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

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("dashagent.llm_client.requests.post", fake_post)
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
    monkeypatch.delenv("OPENAI_USE_REQUESTS_FALLBACK", raising=False)
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
    monkeypatch.delenv("OPENAI_USE_REQUESTS_FALLBACK", raising=False)
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
    monkeypatch.setenv("OPENAI_USE_REQUESTS_FALLBACK", "1")
    captured = {}

    class FakeResponse:
        ok = True

        def json(self):
            return {
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 3},
            }

    def fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["data"] = data
        return FakeResponse()

    monkeypatch.setattr("dashagent.llm_client.requests.post", fake_post)
    client = OpenRouterLLMClient(api_key="unit-test-openrouter-key", model="openai/gpt-4o-mini")
    result = client.generate_messages([{"role": "user", "content": "hello"}])
    assert result["ok"] is True
    assert result["provider"] == "openrouter"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert "unit-test-openrouter-key" not in str(result)
