from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .concise_rewrite_card import ConciseRewriteCard
from .llm_client import get_llm_client
from .trajectory import estimate_tokens


@dataclass(frozen=True)
class ConciseRewriteResult:
    rewritten_answer: str
    category: str
    attempted: bool
    backend_available: bool
    raw_response_present: bool = False
    extracted_content_length: int = 0
    exception_class: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rewritten_answer": self.rewritten_answer,
            "category": self.category,
            "attempted": self.attempted,
            "backend_available": self.backend_available,
            "raw_response_present": self.raw_response_present,
            "extracted_content_length": self.extracted_content_length,
            "exception_class": self.exception_class,
            "debug": self.debug,
        }


def rewrite_concise_answer(
    card: ConciseRewriteCard,
    *,
    llm_client: Any | None = None,
    max_tokens: int = 96,
) -> ConciseRewriteResult:
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception as exc:
            return ConciseRewriteResult(
                rewritten_answer="",
                category="backend_unavailable",
                attempted=True,
                backend_available=False,
                exception_class=type(exc).__name__,
                debug={"client_construction_failed": True},
            )
    if client is None or (hasattr(client, "available") and not bool(client.available())):
        return ConciseRewriteResult(
            rewritten_answer="",
            category="backend_unavailable",
            attempted=True,
            backend_available=False,
            debug={"client_available": False},
        )

    messages = _messages(card)
    debug = {
        "request_message_count": len(messages),
        "estimated_prompt_tokens": sum(estimate_tokens(str(message.get("content", ""))) for message in messages),
        "max_answer_tokens": max_tokens,
        "answer_type": card.answer_type,
    }
    try:
        raw = _call_client(client, messages, max_tokens=max_tokens)
        raw_shape = _raw_shape(raw)
        if isinstance(raw, dict) and raw.get("ok") is False:
            return ConciseRewriteResult(
                rewritten_answer="",
                category="backend_unavailable",
                attempted=True,
                backend_available=True,
                raw_response_present=True,
                extracted_content_length=0,
                exception_class=str(raw.get("error_category") or "LLMBackendError"),
                debug={**debug, "raw_response_shape": raw_shape},
            )
        answer = _extract_content(raw)
    except Exception as exc:
        return ConciseRewriteResult(
            rewritten_answer="",
            category="backend_unavailable",
            attempted=True,
            backend_available=True,
            exception_class=type(exc).__name__,
            debug=debug,
        )
    if not answer:
        return ConciseRewriteResult(
            rewritten_answer="",
            category="empty_rewrite",
            attempted=True,
            backend_available=True,
            raw_response_present=raw is not None,
            extracted_content_length=0,
            debug={**debug, "raw_response_shape": raw_shape},
        )
    return ConciseRewriteResult(
        rewritten_answer=answer,
        category="ok",
        attempted=True,
        backend_available=True,
        raw_response_present=True,
        extracted_content_length=len(answer),
        debug={**debug, "raw_response_shape": raw_shape},
    )


def _messages(card: ConciseRewriteCard) -> list[dict[str, Any]]:
    payload = card.to_dict()
    return [
        {
            "role": "system",
            "content": (
                "Rewrite the legacy answer into a concise final answer using only the provided exact facts. "
                "Return final answer text only. Do not include JSON or reasoning."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "card": payload,
                    "rewrite_rules": [
                        "One sentence max unless a compact semicolon list is needed.",
                        "Use exact values from exact_facts.",
                        "Prefer the user's object phrase.",
                        "Do not explain unless the prompt asks why/how/explain.",
                        "Do not start with Based on the evidence.",
                        "Do not say appears to unless evidence is uncertain.",
                        "Do not add local/live/API caveats unless card.exact_facts.caveats includes them.",
                    ],
                    "examples": {
                        "COUNT": "74 schemas.",
                        "DATE": "Birthday Message was published on 2026-03-31.",
                        "STATUS": "Birthday Message is inactive.",
                        "LIST": "Inactive journeys: Birthday Message; Gold Tier Welcome Email.",
                    },
                },
                sort_keys=True,
            ),
        },
    ]


def _call_client(client: Any, messages: list[dict[str, Any]], *, max_tokens: int) -> Any:
    if hasattr(client, "complete"):
        try:
            return client.complete(messages, max_tokens=max_tokens)
        except TypeError:
            return client.complete(messages)
    if hasattr(client, "chat"):
        try:
            return client.chat(messages, max_tokens=max_tokens)
        except TypeError:
            return client.chat(messages)
    if hasattr(client, "generate_messages"):
        try:
            return client.generate_messages(messages, max_tokens=max_tokens)
        except TypeError:
            return client.generate_messages(messages)
    if hasattr(client, "complete_json"):
        return client.complete_json(messages)
    raise TypeError("unsupported concise rewrite client")


def _extract_content(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if not isinstance(raw, dict) and hasattr(raw, "model_dump"):
        try:
            raw = raw.model_dump()
        except Exception:
            return ""
    if not isinstance(raw, dict) and hasattr(raw, "to_dict"):
        try:
            raw = raw.to_dict()
        except Exception:
            return ""
    if not isinstance(raw, dict):
        return ""
    candidates: list[str] = []
    for key in ("content", "output_text", "answer", "text"):
        value = raw.get(key)
        if isinstance(value, str):
            candidates.append(value)
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    candidates.append(content)
                elif isinstance(content, list):
                    candidates.extend(_content_blocks(content))
            if isinstance(first.get("text"), str):
                candidates.append(first["text"])
    output = raw.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, list):
                    candidates.extend(_content_blocks(content))
                elif isinstance(content, str):
                    candidates.append(content)
    return "\n".join(value.strip() for value in candidates if value and value.strip()).strip()


def _raw_shape(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"type": "NoneType"}
    if not isinstance(raw, dict) and hasattr(raw, "model_dump"):
        try:
            raw = raw.model_dump()
        except Exception:
            return {"type": type(raw).__name__, "model_dump_failed": True}
    if not isinstance(raw, dict):
        return {"type": type(raw).__name__}
    shape: dict[str, Any] = {
        "type": "dict",
        "keys": sorted(str(key) for key in raw.keys())[:12],
        "ok": raw.get("ok"),
        "finish_reason": raw.get("finish_reason"),
        "content_present": bool(raw.get("content")),
        "output_text_present": bool(raw.get("output_text")),
        "error_category": raw.get("error_category"),
    }
    choices = raw.get("choices")
    if isinstance(choices, list):
        shape["choices_count"] = len(choices)
    return shape


def _content_blocks(blocks: list[Any]) -> list[str]:
    values: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = block.get("text") or block.get("content")
        if isinstance(text, str):
            values.append(text)
    return values
