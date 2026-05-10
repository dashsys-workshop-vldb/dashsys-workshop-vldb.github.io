from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from .trajectory import compact_preview, redact_secrets

try:  # Optional at import time so tests and request fallback remain usable.
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - exercised when dependency is absent.
    OpenAI = None  # type: ignore


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

_KEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
_AUTH_HEADER_RE = re.compile(r"Authorization\s*:\s*" + r"Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE)


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
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_seconds = timeout_seconds
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).rstrip("/")
        self.endpoint = os.getenv("OPENAI_CHAT_COMPLETIONS_URL") or f"{self.base_url}/chat/completions"
        self.provider = "openai"
        self.missing_key_reason = "OPENAI_API_KEY is not set"
        self._sdk_client: Any | None = None

    def sdk_available(self) -> bool:
        return OpenAI is not None and os.getenv("OPENAI_USE_REQUESTS_FALLBACK", "0") != "1"

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
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2048")),
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        try:
            if self.sdk_available():
                body = self._create_with_sdk(payload)
                response_ok = True
                transport = "openai_sdk"
            else:
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
                response_ok = response.ok
                transport = "requests_fallback"
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
                "transport": "openai_sdk" if self.sdk_available() else "requests_fallback",
                "error": _redact_error_text(str(exc))[:500],
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
        result = redact_secrets(
            {
                "ok": response_ok,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "base_url": self.base_url,
                "transport": transport,
                "content": content,
                "tool_calls": tool_calls,
                "message": compact_preview(message, 2000),
                "finish_reason": finish_reason,
                "usage": body.get("usage", {}),
                "raw_preview": compact_preview(body, 1200),
                "error": None if response_ok else _redact_error_text(str(body))[:500],
                "tool_call_warning": _tool_call_warning(tools, tool_choice, tool_calls, response_ok),
            }
        )
        result["provider"] = self.provider_name()
        result["model"] = self.model_name()
        result["base_url"] = self.base_url
        return result

    def _create_with_sdk(self, payload: dict[str, Any]) -> dict[str, Any]:
        if OpenAI is None:  # pragma: no cover - guarded by sdk_available.
            raise RuntimeError("OpenAI SDK is not installed")
        if self._sdk_client is None:
            self._sdk_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
        completion = self._sdk_client.chat.completions.create(**payload)
        if hasattr(completion, "model_dump"):
            return completion.model_dump()
        if hasattr(completion, "dict"):
            return completion.dict()
        return json.loads(json.dumps(completion, default=lambda obj: getattr(obj, "__dict__", str(obj))))


class OpenRouterLLMClient(OpenAILLMClient):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        self.timeout_seconds = timeout_seconds
        root = (base_url or os.getenv("OPENROUTER_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
        self.base_url = root
        self.endpoint = f"{root}/chat/completions"
        self.provider = "openrouter"
        self.missing_key_reason = "OPENROUTER_API_KEY is not set"
        self._sdk_client = None


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


def _redact_error_text(text: str) -> str:
    redacted = redact_secrets(text)
    if not isinstance(redacted, str):
        redacted = str(redacted)
    redacted = _AUTH_HEADER_RE.sub("Authorization: " + "Bearer [REDACTED]", redacted)
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
    redacted = _KEY_LIKE_RE.sub("[REDACTED]", redacted)
    return redacted


def get_llm_client(provider: str | None = None) -> LLMClient:
    selected = (provider or os.getenv("LLM_PROVIDER") or "").strip().lower()
    if not selected:
        openai_base_url = os.getenv("OPENAI_BASE_URL", "")
        if os.getenv("OPENAI_API_KEY") and openai_base_url and "openrouter.ai" not in openai_base_url:
            selected = "openai"
        elif os.getenv("OPENROUTER_API_KEY") or "openrouter.ai" in openai_base_url:
            selected = "openrouter"
        else:
            selected = "openai"
    if selected == "openrouter":
        client: OpenAILLMClient = OpenRouterLLMClient()
    elif selected == "openai":
        client = OpenAILLMClient()
    else:
        return NoOpLLMClient(reason=f"Unsupported LLM_PROVIDER: {selected}", model=DEFAULT_OPENAI_MODEL)
    if client.available():
        return client
    return NoOpLLMClient(reason=client.missing_key_reason, model=client.model_name())
