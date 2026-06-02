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

try:  # Optional at import time; Gemini support is enabled only when configured.
    from google import genai as _google_genai  # type: ignore
    from google.genai import types as GeminiTypes  # type: ignore

    GeminiSDKClient = _google_genai.Client  # type: ignore
except Exception:  # pragma: no cover - exercised when dependency is absent.
    GeminiSDKClient = None  # type: ignore
    GeminiTypes = None  # type: ignore


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_PIONEER_MODEL = "gpt-4o"
DEFAULT_PIONEER_BASE_URL = "https://api.pioneer.ai/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

_KEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9_*.-]{8,}")
_AUTH_HEADER_RE = re.compile(r"Authorization\s*:\s*" + r"Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE)


def _configured_timeout_seconds(default: int, *env_names: str) -> int:
    for name in env_names:
        raw = os.getenv(name)
        if not raw:
            continue
        try:
            value = int(raw)
        except Exception:
            continue
        if value > 0:
            return value
    return int(default)


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
        parallel_tool_calls: bool | None = None,
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
        parallel_tool_calls: bool | None = None,
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
        self.timeout_seconds = _configured_timeout_seconds(timeout_seconds, "HERMES_LLM_CALL_TIMEOUT_SEC", "LLM_TIMEOUT_SECONDS")
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
        parallel_tool_calls: bool | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            return NoOpLLMClient(reason=self.missing_key_reason, model=self.model).generate_messages(
                messages, tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2048")),
        }
        if tools:
            payload["tools"] = tools
            if parallel_tool_calls is not None:
                payload["parallel_tool_calls"] = bool(parallel_tool_calls)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        try:
            body = self._create_with_sdk(payload)
            response_ok = True
            transport = "openai_sdk"
        except Exception as exc:
            redacted_error = _redact_error_text(str(exc))[:500]
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
                "error": redacted_error,
                "error_category": _classify_llm_error_text(str(exc)),
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


class PioneerChatLLMClient(OpenAILLMClient):
    """OpenAI SDK-compatible chat client for Pioneer no-tool LLM access."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("PIONEER_API_KEY")
        self.model = model or os.getenv("PIONEER_MODEL_ID") or os.getenv("PIONEER_MODEL", DEFAULT_PIONEER_MODEL)
        timeout_value = timeout_seconds if timeout_seconds is not None else int(os.getenv("PIONEER_TIMEOUT_SEC", "60"))
        self.timeout_seconds = timeout_value
        self.base_url = (base_url or os.getenv("PIONEER_BASE_URL") or DEFAULT_PIONEER_BASE_URL).rstrip("/")
        self.provider = "pioneer_chat"
        self.missing_key_reason = "PIONEER_API_KEY is not set"
        self._sdk_client = None

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
        )

    def generate_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            return NoOpLLMClient(reason=self.missing_key_reason, model=self.model).generate_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens if max_tokens is not None else os.getenv("LLM_MAX_TOKENS", "512")),
        }
        store_value = os.getenv("PIONEER_STORE")
        if store_value is not None:
            payload["store"] = store_value.strip().lower() not in {"0", "false", "no", "off"}
        try:
            body = self._create_with_sdk(payload)
        except Exception as exc:
            if "store" in payload and _pioneer_store_field_rejected(str(exc)):
                payload_without_store = dict(payload)
                payload_without_store.pop("store", None)
                try:
                    body = self._create_with_sdk(payload_without_store)
                except Exception as retry_exc:
                    exc = retry_exc
                else:
                    return self._pioneer_result_from_body(
                        body,
                        tools=tools,
                        tool_choice=tool_choice,
                        parallel_tool_calls=parallel_tool_calls,
                        store_field_retry=True,
                    )
            redacted_error = _redact_error_text(str(exc))[:500]
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
                "error": redacted_error,
                "error_category": _classify_llm_error_text(str(exc)),
                "tool_call_warning": "pioneer_chat_no_native_tool_calling" if tools or tool_choice else None,
            }
        return self._pioneer_result_from_body(
            body,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            store_field_retry=False,
        )

    def _pioneer_result_from_body(
        self,
        body: dict[str, Any],
        *,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        parallel_tool_calls: bool | None,
        store_field_retry: bool,
    ) -> dict[str, Any]:
        try:
            choice = body["choices"][0]
            message = choice.get("message") or {}
            if not isinstance(message, dict) or "content" not in message:
                raise KeyError("choices[0].message.content")
            content = message.get("content") or ""
            finish_reason = choice.get("finish_reason")
        except Exception as exc:
            return {
                "ok": False,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "base_url": self.base_url,
                "transport": "openai_sdk",
                "backend_type": "openai_sdk",
                "sdk_path_used": True,
                "content": "",
                "tool_calls": [],
                "message": {},
                "finish_reason": None,
                "usage": body.get("usage", {}) if isinstance(body, dict) else {},
                "raw_preview": compact_preview(body, 1200),
                "error": _redact_error_text(f"Pioneer response missing {exc}")[:500],
                "error_category": "response_parse_failed",
                "tool_call_warning": "pioneer_chat_no_native_tool_calling" if tools or tool_choice else None,
            }
        result = redact_secrets(
            {
                "ok": True,
                "skipped": False,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "base_url": self.base_url,
                "transport": "openai_sdk",
                "backend_type": "openai_sdk",
                "sdk_path_used": True,
                "content": content,
                "tool_calls": [],
                "message": compact_preview(message, 2000),
                "finish_reason": finish_reason,
                "usage": body.get("usage", {}),
                "raw_preview": compact_preview(body, 1200),
                "error": None,
                "response_shape": "choices[0].message.content",
                "store_field_retry": store_field_retry,
                "tool_call_warning": "pioneer_chat_no_native_tool_calling" if tools or tool_choice or parallel_tool_calls else None,
            }
        )
        result["provider"] = self.provider_name()
        result["model"] = self.model_name()
        result["base_url"] = self.base_url
        return result

    def complete_text(
        self,
        system_prompt: str | list[dict[str, Any]],
        user_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        messages = _messages_from_prompt(system_prompt, user_prompt)
        result = self.generate_messages(messages, temperature=temperature, max_tokens=max_tokens)
        if not result.get("ok"):
            reason = result.get("error") or result.get("reason") or "Pioneer chat completion failed"
            raise RuntimeError(str(reason))
        return str(result.get("content") or "").strip()

    def complete_json(
        self,
        system_prompt: str | list[dict[str, Any]],
        user_prompt: str | None = None,
        schema_hint: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        messages = _json_messages_from_prompt(system_prompt, user_prompt, schema_hint)
        try:
            text = self.complete_text(messages, temperature=temperature, max_tokens=max_tokens)
            return json.loads(_strip_json_text(text))
        except Exception:
            return _conservative_json_fallback()


class GeminiLLMClient(LLMClient):
    """Google GenAI SDK client normalized to the shared LLMClient shape."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        timeout_value = timeout_seconds if timeout_seconds is not None else int(os.getenv("GEMINI_TIMEOUT_SEC", "60"))
        self.timeout_seconds = _configured_timeout_seconds(timeout_value, "GEMINI_TIMEOUT_SEC", "HERMES_LLM_CALL_TIMEOUT_SEC", "LLM_TIMEOUT_SECONDS")
        self.provider = "gemini"
        self._sdk_client: Any | None = None
        self.missing_key_reason = self._unavailable_reason()

    def sdk_available(self) -> bool:
        return GeminiSDKClient is not None and GeminiTypes is not None

    def available(self) -> bool:
        return bool(self.api_key) and self.sdk_available()

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
        parallel_tool_calls: bool | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            return NoOpLLMClient(reason=self._unavailable_reason(), model=self.model).generate_messages(
                messages, tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls
            )
        system_instruction, contents = _gemini_contents(messages)
        config = _gemini_generate_config(
            system_instruction=system_instruction,
            tools=tools,
            tool_choice=tool_choice,
            timeout_seconds=self.timeout_seconds,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        )
        try:
            response = self._generate_content_with_sdk(
                {
                    "model": self.model,
                    "contents": contents,
                    "config": config,
                }
            )
        except Exception as exc:
            redacted_error = _redact_error_text(str(exc))[:500]
            return {
                "ok": False,
                "skipped": False,
                "provider": self.provider,
                "model": self.model_name(),
                "transport": "gemini_sdk",
                "backend_type": "gemini_sdk",
                "sdk_path_used": True,
                "content": "",
                "tool_calls": [],
                "message": {},
                "finish_reason": None,
                "usage": {},
                "error": redacted_error,
                "error_category": _classify_llm_error_text(str(exc)),
            }
        content = str(getattr(response, "text", "") or "")
        tool_calls = _normalize_gemini_tool_calls(response)
        finish_reason = _gemini_finish_reason(response, tool_calls)
        usage = _normalize_gemini_usage(getattr(response, "usage_metadata", None))
        result = redact_secrets(
            {
                "ok": True,
                "skipped": False,
                "provider": self.provider,
                "model": self.model_name(),
                "transport": "gemini_sdk",
                "backend_type": "gemini_sdk",
                "sdk_path_used": True,
                "content": content,
                "tool_calls": tool_calls,
                "message": compact_preview(_gemini_response_preview(response), 2000),
                "finish_reason": finish_reason,
                "usage": usage,
                "raw_preview": compact_preview(_gemini_response_preview(response), 1200),
                "error": None,
                "tool_call_warning": _tool_call_warning(tools, tool_choice, tool_calls, True),
            }
        )
        result["provider"] = self.provider
        result["model"] = self.model_name()
        return result

    def _generate_content_with_sdk(self, payload: dict[str, Any]) -> Any:
        if GeminiSDKClient is None:
            raise RuntimeError("Google Gen AI SDK is not installed")
        if self._sdk_client is None:
            self._sdk_client = GeminiSDKClient(api_key=self.api_key)
        return self._sdk_client.models.generate_content(**payload)

    def _unavailable_reason(self) -> str:
        if not self.api_key:
            return "GEMINI_API_KEY is not set"
        if not self.sdk_available():
            return "Google Gen AI SDK is not installed"
        return "Gemini client is unavailable"


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
        parallel_tool_calls: bool | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            return NoOpLLMClient(reason=self.missing_key_reason, model=self.model).generate_messages(
                messages, tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls
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
            redacted_error = _redact_error_text(str(exc))[:500]
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
                "error": redacted_error,
                "error_category": _classify_llm_error_text(str(exc)),
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


def _messages_from_prompt(
    system_prompt: str | list[dict[str, Any]],
    user_prompt: str | None = None,
) -> list[dict[str, Any]]:
    if isinstance(system_prompt, list):
        return [dict(message) for message in system_prompt if isinstance(message, dict)]
    return [
        {"role": "system", "content": str(system_prompt)},
        {"role": "user", "content": "" if user_prompt is None else str(user_prompt)},
    ]


def _json_messages_from_prompt(
    system_prompt: str | list[dict[str, Any]],
    user_prompt: str | None = None,
    schema_hint: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    json_instruction = "Return ONLY valid JSON. No markdown. No explanation. No code fence."
    messages = _messages_from_prompt(system_prompt, user_prompt)
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = f"{messages[0].get('content', '')}\n\n{json_instruction}".strip()
    else:
        messages.insert(0, {"role": "system", "content": json_instruction})
    if schema_hint:
        messages.append({"role": "user", "content": "JSON schema hint: " + json.dumps(schema_hint, sort_keys=True)})
    return messages


def _strip_json_text(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _conservative_json_fallback() -> dict[str, Any]:
    return {
        "intent": "UNKNOWN",
        "route": "EVIDENCE_PIPELINE",
        "requires_evidence": True,
        "pure_no_evidence": False,
        "confidence": 0.0,
        "parse_error": True,
    }


def _gemini_contents(messages: list[dict[str, Any]]) -> tuple[str | None, str]:
    system_parts: list[str] = []
    content_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        if role == "system":
            if content:
                system_parts.append(content)
        elif role == "assistant":
            content_parts.append(f"Assistant: {content}")
        elif role == "tool":
            content_parts.append(f"Tool result: {content}")
        else:
            content_parts.append(content)
    return ("\n\n".join(system_parts) if system_parts else None, "\n\n".join(part for part in content_parts if part).strip())


def _gemini_generate_config(
    *,
    system_instruction: str | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    timeout_seconds: int,
    max_tokens: int,
) -> Any:
    if GeminiTypes is None:
        return None
    kwargs: dict[str, Any] = {
        "temperature": 0,
        "max_output_tokens": max_tokens,
    }
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    gemini_tools = _gemini_tools(tools)
    if gemini_tools:
        kwargs["tools"] = gemini_tools
    tool_config = _gemini_tool_config(tool_choice)
    if tool_config is not None:
        kwargs["tool_config"] = tool_config
    http_options = _gemini_http_options(timeout_seconds)
    if http_options is not None:
        kwargs["http_options"] = http_options
    return GeminiTypes.GenerateContentConfig(**kwargs)


def _gemini_tools(tools: list[dict[str, Any]] | None) -> list[Any]:
    if GeminiTypes is None:
        return []
    declarations: list[Any] = []
    for tool in tools or []:
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = function.get("name")
        if not name:
            continue
        declarations.append(
            GeminiTypes.FunctionDeclaration(
                name=name,
                description=function.get("description") or "",
                parameters_json_schema=function.get("parameters") or {"type": "object", "properties": {}},
            )
        )
    if not declarations:
        return []
    return [GeminiTypes.Tool(function_declarations=declarations)]


def _gemini_tool_config(tool_choice: str | dict[str, Any] | None) -> Any | None:
    if GeminiTypes is None or not hasattr(GeminiTypes, "ToolConfig") or not hasattr(GeminiTypes, "FunctionCallingConfig"):
        return None
    allowed_names: list[str] | None = None
    mode = None
    if tool_choice == "required":
        mode = "ANY"
    elif isinstance(tool_choice, dict):
        function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
        name = function.get("name")
        if name:
            mode = "ANY"
            allowed_names = [str(name)]
    elif tool_choice == "none":
        mode = "NONE"
    elif tool_choice == "auto":
        mode = "AUTO"
    if mode is None:
        return None
    try:
        calling_config_kwargs: dict[str, Any] = {"mode": mode}
        if allowed_names:
            calling_config_kwargs["allowed_function_names"] = allowed_names
        function_calling_config = GeminiTypes.FunctionCallingConfig(**calling_config_kwargs)
        return GeminiTypes.ToolConfig(function_calling_config=function_calling_config)
    except Exception:
        return None


def _gemini_http_options(timeout_seconds: int) -> Any | None:
    if GeminiTypes is None or not hasattr(GeminiTypes, "HttpOptions"):
        return None
    try:
        return GeminiTypes.HttpOptions(timeout=int(timeout_seconds * 1000))
    except Exception:
        return None


def _normalize_gemini_tool_calls(response: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for index, call in enumerate(getattr(response, "function_calls", None) or []):
        name = getattr(call, "name", None) or _maybe_mapping_get(call, "name")
        args = getattr(call, "args", None)
        if args is None:
            args = _maybe_mapping_get(call, "args") or {}
        if not isinstance(args, dict):
            args = dict(args) if hasattr(args, "items") else {"_raw": str(args)}
        raw_arguments = json.dumps(args, default=str)
        calls.append(
            {
                "id": getattr(call, "id", None) or _maybe_mapping_get(call, "id") or f"gemini_call_{index + 1}",
                "type": "function",
                "tool": name,
                "name": name,
                "arguments": args,
                "raw_arguments": raw_arguments,
            }
        )
    return calls


def _maybe_mapping_get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    if hasattr(value, "get"):
        try:
            return value.get(key)
        except Exception:
            return None
    return None


def _gemini_finish_reason(response: Any, tool_calls: list[dict[str, Any]]) -> str | None:
    if tool_calls:
        return "tool_calls"
    candidates = getattr(response, "candidates", None) or []
    first = candidates[0] if candidates else None
    reason = getattr(first, "finish_reason", None) if first is not None else None
    return str(reason) if reason is not None else None


def _normalize_gemini_usage(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        try:
            usage = usage.model_dump()
        except Exception:
            pass
    if hasattr(usage, "dict"):
        try:
            usage = usage.dict()
        except Exception:
            pass
    if not isinstance(usage, dict):
        usage = getattr(usage, "__dict__", {})
    if not isinstance(usage, dict):
        return {}
    normalized = dict(usage)
    input_tokens = normalized.get("prompt_token_count") or normalized.get("input_tokens")
    output_tokens = normalized.get("candidates_token_count") or normalized.get("output_tokens")
    total_tokens = normalized.get("total_token_count") or normalized.get("total_tokens")
    if total_tokens is None and isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
        total_tokens = int(input_tokens + output_tokens)
    if total_tokens is not None:
        normalized["total_tokens"] = int(total_tokens)
    return normalized


def _gemini_response_preview(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump()
            return dumped if isinstance(dumped, dict) else {"response": dumped}
        except Exception:
            pass
    preview: dict[str, Any] = {
        "text_present": bool(getattr(response, "text", None)),
        "function_calls_count": len(getattr(response, "function_calls", None) or []),
        "finish_reason": _gemini_finish_reason(response, _normalize_gemini_tool_calls(response)),
        "usage": _normalize_gemini_usage(getattr(response, "usage_metadata", None)),
    }
    return preview


def _pioneer_store_field_rejected(text: str) -> bool:
    lower = str(text or "").lower()
    return "store" in lower and any(marker in lower for marker in ("unknown", "unexpected", "extra", "unrecognized", "not permitted"))


def _classify_llm_error_text(text: str) -> str:
    lower = str(text or "").lower()
    if any(marker in lower for marker in ("401", "403", "unauthorized", "forbidden", "invalid api key", "incorrect api key", "authentication", "auth")):
        return "auth_or_401"
    if any(marker in lower for marker in ("429", "rate limit", "rate_limit", "too many requests")):
        return "rate_limited_or_429"
    if any(marker in lower for marker in ("insufficient_quota", "quota", "billing")):
        return "quota_or_billing"
    if any(
        marker in lower
        for marker in (
            "model_not_found",
            "model not found",
            "does not exist",
            "invalid model",
            "unknown model",
            "not a recognised model id",
            "not a recognized model id",
        )
    ):
        return "model_not_found"
    if any(marker in lower for marker in ("timeout", "timed out", "readtimeout")):
        return "timeout"
    if any(marker in lower for marker in ("enotfound", "dns", "name resolution", "connection", "connect", "network")):
        return "network_error"
    return "provider_error"


def get_llm_client(provider: str | None = None) -> LLMClient:
    selected = (provider or os.getenv("DASHAGENT_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "").strip().lower()
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
    elif selected == "pioneer_chat":
        client = PioneerChatLLMClient()
    elif selected == "gemini":
        client = GeminiLLMClient()
    else:
        return NoOpLLMClient(reason=f"Unsupported LLM_PROVIDER: {selected}", model=DEFAULT_OPENAI_MODEL)
    if client.available():
        return client
    return NoOpLLMClient(reason=getattr(client, "missing_key_reason", "LLM provider API key is not set"), model=client.model_name())
