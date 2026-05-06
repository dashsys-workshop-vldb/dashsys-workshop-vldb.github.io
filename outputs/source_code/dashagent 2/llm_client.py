from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from .trajectory import compact_preview, redact_secrets


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMClient:
    def available(self) -> bool:
        raise NotImplementedError

    def provider_name(self) -> str:
        raise NotImplementedError

    def model_name(self) -> str:
        raise NotImplementedError

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def generate_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class NoOpLLMClient(LLMClient):
    reason: str = "OPENAI_API_KEY is not set"
    model: str = DEFAULT_OPENAI_MODEL

    def available(self) -> bool:
        return False

    def provider_name(self) -> str:
        return "none"

    def model_name(self) -> str:
        return self.model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.generate_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            tool_choice="auto" if tools else None,
        )

    def generate_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "skipped": True,
            "reason": self.reason,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": "",
            "tool_calls": [],
            "message": {},
            "finish_reason": None,
            "usage": {},
        }


class OpenAILLMClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_seconds = timeout_seconds
        self.endpoint = os.getenv("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
        self.provider = "openai"
        self.missing_key_reason = "OPENAI_API_KEY is not set"

    def available(self) -> bool:
        return bool(self.api_key)

    def provider_name(self) -> str:
        return self.provider if self.available() else "none"

    def model_name(self) -> str:
        return self.model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.generate_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            tool_choice="auto" if tools else None,
        )

    def generate_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            return NoOpLLMClient(reason=self.missing_key_reason, model=self.model).generate_messages(
                messages, tools=tools, tool_choice=tool_choice
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=self.timeout_seconds,
            )
            body = response.json()
        except Exception as exc:
            return {
                "ok": False,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "content": "",
                "tool_calls": [],
                "message": {},
                "finish_reason": None,
                "usage": {},
                "error": str(exc)[:500],
            }
        content = ""
        tool_calls: list[dict[str, Any]] = []
        message: dict[str, Any] = {}
        finish_reason = None
        try:
            choice = body["choices"][0]
            message = choice.get("message") or {}
            finish_reason = choice.get("finish_reason")
            content = message.get("content") or ""
            tool_calls = _normalize_openai_tool_calls(message)
        except Exception:
            content = ""
        return redact_secrets(
            {
                "ok": response.ok,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "content": content,
                "tool_calls": tool_calls,
                "message": compact_preview(message, 2000),
                "finish_reason": finish_reason,
                "usage": body.get("usage", {}),
                "raw_preview": compact_preview(body, 1200),
                "error": None if response.ok else str(body)[:500],
                "tool_call_warning": _tool_call_warning(tools, tool_choice, tool_calls, response.ok),
            }
        )


class OpenRouterLLMClient(OpenAILLMClient):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        self.timeout_seconds = timeout_seconds
        root = (base_url or os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL)).rstrip("/")
        self.endpoint = f"{root}/chat/completions"
        self.provider = "openrouter"
        self.missing_key_reason = "OPENROUTER_API_KEY is not set"


def _tool_call_warning(
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    tool_calls: list[dict[str, Any]],
    response_ok: bool,
) -> str | None:
    if not response_ok or not tools or tool_calls:
        return None
    if tool_choice == "required" or isinstance(tool_choice, dict):
        return "model_did_not_return_tool_calls"
    return None


def _normalize_openai_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        arguments: Any = raw_arguments
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except Exception:
                arguments = {"_raw": raw_arguments}
        tool_calls.append(
            {
                "id": raw_call.get("id"),
                "type": raw_call.get("type") or "function",
                "tool": function.get("name"),
                "name": function.get("name"),
                "arguments": arguments if isinstance(arguments, dict) else {},
                "raw_arguments": raw_arguments if isinstance(raw_arguments, str) else json.dumps(raw_arguments, default=str),
            }
        )
    return tool_calls


def get_llm_client(provider: str | None = None) -> LLMClient:
    selected = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    if selected == "openrouter":
        client: OpenAILLMClient = OpenRouterLLMClient()
    elif selected == "openai":
        client = OpenAILLMClient()
    else:
        return NoOpLLMClient(reason=f"Unsupported LLM_PROVIDER: {selected}", model=DEFAULT_OPENAI_MODEL)
    if client.available():
        return client
    return NoOpLLMClient(reason=client.missing_key_reason, model=client.model_name())
