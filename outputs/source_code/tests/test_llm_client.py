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


def test_openai_generate_messages_normalizes_native_tool_calls(monkeypatch):
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
    client = OpenAILLMClient(api_key="sk-test")
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


def test_openrouter_generate_messages_uses_openrouter_endpoint(monkeypatch):
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
    client = OpenRouterLLMClient(api_key="sk-or-test", model="openai/gpt-4o-mini")
    result = client.generate_messages([{"role": "user", "content": "hello"}])
    assert result["ok"] is True
    assert result["provider"] == "openrouter"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert "sk-or-test" not in str(result)
