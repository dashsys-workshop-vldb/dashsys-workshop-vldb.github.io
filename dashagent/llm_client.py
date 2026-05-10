from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from .trajectory import compact_preview, redact_secrets

try:  # Optional at import time so tests remain usable when SDKs are absent.
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - exercised when dependency is absent.
    OpenAI = None  # type: ignore

try:  # Optional at import time; Anthropic is a shadow/comparison backend.
    from anthropic import Anthropic  # type: ignore
except Exception:  # pragma: no cover - exercised when dependency is absent.
    Anthropic = None  # type: ignore


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"

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
            "backend_type": "none",
            "sdk_path_used": False,
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
        self.provider = "openai"
        self.missing_key_reason = "OPENAI_API_KEY is not set"
        self._sdk_client: Any | None = None

    def sdk_available(self) -> bool:
        return OpenAI is not None

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
            body = self._create_with_sdk(payload)
            response_ok = True
            transport = "openai_sdk"
        except Exception as exc:
            return {
                "ok": False,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "backend_type": "openai_sdk",
                "sdk_path_used": True,
                "content": "",
                "tool_calls": [],
                "message": {},
                "finish_reason": None,
                "usage": {},
                "transport": "openai_sdk",
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
                "backend_type": "openai_sdk",
                "sdk_path_used": True,
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
        self.provider = "openrouter"
        self.missing_key_reason = "OPENROUTER_API_KEY is not set"
        self._sdk_client = None


class AnthropicLLMClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.timeout_seconds = timeout_seconds
        self.provider = "anthropic"
        self.missing_key_reason = "ANTHROPIC_API_KEY is not set"
        self._sdk_client: Any | None = None

    def available(self) -> bool:
        return bool(self.api_key)

    def sdk_available(self) -> bool:
        return Anthropic is not None

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
        payload = _anthropic_payload(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            model=self.model,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        )
        try:
            body = self._create_with_sdk(payload)
            response_ok = True
        except Exception as exc:
            return {
                "ok": False,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "base_url": self.base_url,
                "transport": "anthropic_sdk",
                "backend_type": "anthropic_sdk",
                "sdk_path_used": True,
                "content": "",
                "tool_calls": [],
                "message": {},
                "finish_reason": None,
                "usage": {},
                "error": _redact_error_text(str(exc))[:500],
            }
        content = _anthropic_text_content(body)
        tool_calls = _normalize_anthropic_tool_calls(body)
        stop_reason = body.get("stop_reason")
        finish_reason = "tool_calls" if stop_reason == "tool_use" or tool_calls else stop_reason
        usage = _normalize_anthropic_usage(body.get("usage", {}))
        result = redact_secrets(
            {
                "ok": response_ok,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "base_url": self.base_url,
                "transport": "anthropic_sdk",
                "backend_type": "anthropic_sdk",
                "sdk_path_used": True,
                "content": content,
                "tool_calls": tool_calls,
                "message": compact_preview(body, 2000),
                "finish_reason": finish_reason,
                "usage": usage,
                "raw_preview": compact_preview(body, 1200),
                "error": None,
                "tool_call_warning": _tool_call_warning(tools, tool_choice, tool_calls, response_ok),
            }
        )
        result["provider"] = self.provider_name()
        result["model"] = self.model_name()
        result["base_url"] = self.base_url
        return result

    def _create_with_sdk(self, payload: dict[str, Any]) -> dict[str, Any]:
        if Anthropic is None:
            raise RuntimeError("Anthropic SDK is not installed")
        if self._sdk_client is None:
            kwargs: dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_seconds}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._sdk_client = Anthropic(**kwargs)
        response = self._sdk_client.messages.create(**payload)
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "dict"):
            return response.dict()
        return json.loads(json.dumps(response, default=lambda obj: getattr(obj, "__dict__", str(obj))))


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


def _anthropic_payload(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            system_parts.append(str(content or ""))
        elif role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.get("tool_call_id") or "call_1",
                            "content": str(content or ""),
                        }
                    ],
                }
            )
        elif role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"type": "text", "text": str(content)})
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                raw_arguments = function.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                except Exception:
                    arguments = {"_raw": raw_arguments}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.get("id") or "call_1",
                        "name": function.get("name"),
                        "input": arguments if isinstance(arguments, dict) else {},
                    }
                )
            converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append({"role": "assistant" if role == "assistant" else "user", "content": str(content or "")})
    payload: dict[str, Any] = {
        "model": model,
        "messages": converted or [{"role": "user", "content": ""}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if system_parts:
        payload["system"] = "\n\n".join(part for part in system_parts if part)
    anthropic_tools = _anthropic_tools(tools)
    if anthropic_tools and tool_choice != "none":
        payload["tools"] = anthropic_tools
        converted_choice = _anthropic_tool_choice(tool_choice)
        if converted_choice:
            payload["tool_choice"] = converted_choice
    return payload


def _anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool in tools or []:
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = function.get("name")
        if not name:
            continue
        converted.append(
            {
                "name": name,
                "description": function.get("description") or "",
                "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return converted


def _anthropic_tool_choice(tool_choice: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if tool_choice in (None, "auto"):
        return {"type": "auto"}
    if tool_choice == "required":
        return {"type": "any"}
    if isinstance(tool_choice, dict):
        function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
        name = function.get("name")
        if name:
            return {"type": "tool", "name": name}
    return None


def _anthropic_text_content(body: dict[str, Any]) -> str:
    chunks: list[str] = []
    for block in body.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text") or ""))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _normalize_anthropic_tool_calls(body: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for block in body.get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        raw_arguments = block.get("input") if isinstance(block.get("input"), dict) else {}
        calls.append(
            {
                "id": block.get("id"),
                "type": "function",
                "tool": block.get("name"),
                "name": block.get("name"),
                "arguments": raw_arguments,
                "raw_arguments": json.dumps(raw_arguments, default=str),
            }
        )
    return calls


def _normalize_anthropic_usage(usage: Any) -> dict[str, Any]:
    if not isinstance(usage, dict):
        return {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    normalized = dict(usage)
    if isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
        normalized["total_tokens"] = int(input_tokens + output_tokens)
    return normalized


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
            selected = "openai_compatible"
        elif os.getenv("OPENROUTER_API_KEY") or "openrouter.ai" in openai_base_url:
            selected = "openrouter"
        elif os.getenv("ANTHROPIC_API_KEY"):
            selected = "anthropic"
        else:
            selected = "openai"
    if selected == "openrouter":
        client: LLMClient = OpenRouterLLMClient()
    elif selected in {"openai", "openai_compatible"}:
        client = OpenAILLMClient()
    elif selected == "anthropic":
        client = AnthropicLLMClient()
    else:
        return NoOpLLMClient(reason=f"Unsupported LLM_PROVIDER: {selected}", model=DEFAULT_OPENAI_MODEL)
    if client.available():
        return client
    return NoOpLLMClient(reason=getattr(client, "missing_key_reason", "LLM provider API key is not set"), model=client.model_name())
