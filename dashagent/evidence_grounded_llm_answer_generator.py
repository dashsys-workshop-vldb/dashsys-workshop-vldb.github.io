from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from .answer_slots import AnswerSlots
from .evidence_bus import EvidenceBus
from .evidence_grounded_final_answer_verifier import FinalAnswerRewriteResult, verify_or_rewrite_final_answer
from .llm_client import get_llm_client
from .trajectory import estimate_tokens, redact_secrets


LLM_BACKEND_UNAVAILABLE = "LLM_BACKEND_UNAVAILABLE"
LLM_BACKEND_AUTH_FAILED = "LLM_BACKEND_AUTH_FAILED"
LLM_BACKEND_RATE_LIMITED = "LLM_BACKEND_RATE_LIMITED"
LLM_BACKEND_QUOTA_OR_BILLING = "LLM_BACKEND_QUOTA_OR_BILLING"
LLM_BACKEND_MODEL_NOT_FOUND = "LLM_BACKEND_MODEL_NOT_FOUND"
LLM_BACKEND_TIMEOUT = "LLM_BACKEND_TIMEOUT"
LLM_BACKEND_NETWORK_ERROR = "LLM_BACKEND_NETWORK_ERROR"
LLM_BACKEND_PROVIDER_ERROR = "LLM_BACKEND_PROVIDER_ERROR"
LLM_REQUEST_NOT_SENT = "LLM_REQUEST_NOT_SENT"
LLM_RAW_RESPONSE_EMPTY = "LLM_RAW_RESPONSE_EMPTY"
CONTENT_FIELD_EXTRACTION_FAILED = "CONTENT_FIELD_EXTRACTION_FAILED"
EXCEPTION_THROWN = "EXCEPTION_THROWN"

_FAILED_RESPONSE_CATEGORY_MAP = {
    "auth_or_401": LLM_BACKEND_AUTH_FAILED,
    "rate_limited_or_429": LLM_BACKEND_RATE_LIMITED,
    "quota_or_billing": LLM_BACKEND_QUOTA_OR_BILLING,
    "model_not_found": LLM_BACKEND_MODEL_NOT_FOUND,
    "timeout": LLM_BACKEND_TIMEOUT,
    "network_error": LLM_BACKEND_NETWORK_ERROR,
    "provider_error": LLM_BACKEND_PROVIDER_ERROR,
}
_BACKEND_FAILURE_CATEGORIES = {
    LLM_BACKEND_AUTH_FAILED,
    LLM_BACKEND_RATE_LIMITED,
    LLM_BACKEND_QUOTA_OR_BILLING,
    LLM_BACKEND_MODEL_NOT_FOUND,
    LLM_BACKEND_TIMEOUT,
    LLM_BACKEND_NETWORK_ERROR,
    LLM_BACKEND_PROVIDER_ERROR,
}


@dataclass(frozen=True)
class AnswerClientCallResult:
    content: str
    debug: dict[str, Any]
    category: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class EvidenceGroundedLLMAnswerResult:
    final_answer: str
    verification: Any
    first_pass_ok: bool
    rewrite_attempted: bool
    rewrite_success: bool
    fallback_used: bool
    llm_backend_used: bool
    generator_error: str | None = None
    generator_category: str | None = None
    debug: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        verification = self.verification.to_dict() if hasattr(self.verification, "to_dict") else self.verification
        return {
            "final_answer": self.final_answer,
            "verification": verification,
            "first_pass_ok": self.first_pass_ok,
            "rewrite_attempted": self.rewrite_attempted,
            "rewrite_success": self.rewrite_success,
            "fallback_used": self.fallback_used,
            "llm_backend_used": self.llm_backend_used,
            "generator_error": self.generator_error,
            "generator_category": self.generator_category,
            "debug": self.debug or {},
            "feedback": self.feedback or {},
        }


def generate_evidence_grounded_llm_answer(
    question: str,
    *,
    deterministic_answer: str,
    slots: AnswerSlots,
    answer_card: Any | None = None,
    evidence_bus: EvidenceBus | dict[str, Any] | None = None,
    llm_client: Any | None = None,
    rewrite_client: Any | None = None,
    use_llm: bool = True,
    verify_final_answer: bool = True,
) -> EvidenceGroundedLLMAnswerResult:
    client = llm_client
    explicit_client = llm_client is not None
    if client is None and use_llm:
        try:
            client = get_llm_client()
        except Exception as exc:
            verified = verify_or_rewrite_final_answer(
                deterministic_answer,
                deterministic_answer=deterministic_answer,
                answer_card=answer_card,
                slots=slots,
                evidence_bus=evidence_bus,
                question=question,
            )
            return _from_rewrite_result(
                verified,
                llm_backend_used=False,
                generator_error=f"{type(exc).__name__}: backend unavailable",
                generator_category=EXCEPTION_THROWN,
                debug=_base_debug(None, [], exception=exc),
            )
    if client is not None and hasattr(client, "available") and not bool(client.available()):
        reason = getattr(client, "reason", None) or "LLM backend unavailable"
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return _from_rewrite_result(
            verified,
            llm_backend_used=False,
            generator_error=str(reason),
            generator_category=LLM_BACKEND_UNAVAILABLE,
            debug=_base_debug(client, []),
        )
    if client is None:
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return _from_rewrite_result(
            verified,
            llm_backend_used=False,
            generator_category=LLM_BACKEND_UNAVAILABLE,
            debug=_base_debug(None, []),
        )
    try:
        call_result = _call_answer_client(client, question, deterministic_answer, slots, answer_card)
    except Exception as exc:
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return _from_rewrite_result(
            verified,
            llm_backend_used=False,
            generator_error=f"{type(exc).__name__}: answer generation failed",
            generator_category=EXCEPTION_THROWN,
            debug=_base_debug(client, [], exception=exc),
        )
    if not explicit_client and _should_try_backend_fallback(call_result):
        call_result = _try_answer_backend_fallbacks(call_result, client, question, deterministic_answer, slots, answer_card)
    generated = call_result.content
    if not str(generated or "").strip():
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return EvidenceGroundedLLMAnswerResult(
            final_answer=verified.final_answer,
            verification=verified.verification,
            first_pass_ok=False,
            rewrite_attempted=False,
            rewrite_success=False,
            fallback_used=True,
            llm_backend_used=True,
            generator_error=call_result.error or call_result.category or LLM_RAW_RESPONSE_EMPTY,
            generator_category=call_result.category or LLM_RAW_RESPONSE_EMPTY,
            debug=call_result.debug,
            feedback={**(verified.feedback or {}), "empty_llm_answer": True},
        )
    if verify_final_answer:
        verified = verify_or_rewrite_final_answer(
            generated,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
            rewrite_client=rewrite_client,
        )
    else:
        verified = verify_or_rewrite_final_answer(
            generated,
            deterministic_answer=generated,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        verified = FinalAnswerRewriteResult(
            final_answer=generated,
            verification=verified.verification,
            first_pass_ok=True,
            rewrite_attempted=False,
            rewrite_success=False,
            fallback_used=False,
            feedback={"verifier_disabled": True, "diagnostic_only": True},
        )
    return _from_rewrite_result(verified, llm_backend_used=True, debug=call_result.debug)


def _call_answer_client(client: Any, question: str, deterministic_answer: str, slots: AnswerSlots, answer_card: Any | None) -> AnswerClientCallResult:
    payload = {
        "question": question,
        "runtime_requested_roles": _runtime_requested_roles(question, slots),
        "exact_facts": _exact_fact_payload(slots),
        "allowed_slots": slots.compact(),
        "fallback_renderer_answer": deterministic_answer,
        "answer_card": answer_card.to_dict() if hasattr(answer_card, "to_dict") else (answer_card if isinstance(answer_card, dict) else {}),
        "answer_requirements": _answer_requirements(question, slots),
        "rules": [
            "Use natural wording.",
            "Use only allowed facts.",
            "Include every available fact that directly answers the runtime_requested_roles.",
            "Prefer exact values from exact_facts over vague summaries.",
            "Do not invent missing counts, IDs, statuses, dates, names, or relationships.",
            "API error is unavailable, not no-data.",
            "Live empty is scoped to the query only.",
            "Return final answer text only.",
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Generate a concise evidence-grounded final answer. Return answer text only. "
                "Do not copy braced fallback renderer text when exact_facts can be rendered naturally."
            ),
        },
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    if hasattr(client, "complete"):
        raw = client.complete(messages)
        return _normalize_answer_client_response(raw, client, messages)
    if hasattr(client, "chat"):
        raw = client.chat(messages)
        return _normalize_answer_client_response(raw, client, messages)
    if hasattr(client, "complete_json"):
        raw = client.complete_json(messages)
        return _normalize_answer_client_response(raw, client, messages)
    if hasattr(client, "generate_messages"):
        raw = client.generate_messages(messages)
        return _normalize_answer_client_response(raw, client, messages)
    raise TypeError("unsupported evidence-grounded answer client")


def _runtime_requested_roles(question: str, slots: AnswerSlots) -> list[str]:
    norm = _norm(question)
    roles: list[str] = []
    if re.search(r"\b(how many|count|counts|total|number of)\b", norm):
        roles.append("count")
    if re.search(r"\b(status|state|active|inactive|failed|succeeded|published|deployed)\b", norm):
        roles.append("status")
    if re.search(r"\b(when|created|updated|modified|published|deployed|timestamp|date|recent|latest)\b", norm):
        roles.append("date")
    if re.search(r"\b(list|show|return|provide|available|records?|which|what|give me)\b", norm) and slots.entity_names:
        roles.append("name")
    if re.search(r"\b(id|ids|identifier)\b", norm) and slots.entity_ids:
        roles.append("id")
    if "local snapshot" in norm:
        roles.append("local_scope")
    if re.search(r"\b(current|live|platform|adobe experience platform|sandbox)\b", norm):
        roles.append("scope")
    if slots.api_error or slots.dry_run:
        roles.append("api_caveat")
    if str(slots.api_evidence_state or "").lower() in {"live_empty", "live_empty_result"}:
        roles.append("live_empty_scope")
    return _dedupe([role for role in roles if role])


def _answer_requirements(question: str, slots: AnswerSlots) -> list[str]:
    roles = set(_runtime_requested_roles(question, slots))
    requirements = ["Include all available facts that directly answer the user's requested roles."]
    if "count" in roles:
        requirements.append("For count questions, include the exact count and scope.")
    if "name" in roles:
        requirements.append("For list/detail questions, include the provided names and IDs when IDs are requested or clarify the entity returned.")
    if "status" in roles:
        requirements.append("For status questions, include entity plus status/state.")
    if "date" in roles:
        requirements.append("For date questions, include the exact date/timestamp when present.")
    if "api_caveat" in roles:
        requirements.append("If API error exists, say live verification is unavailable/error, not no-data.")
    if "live_empty_scope" in roles:
        requirements.append("If live_empty exists, say no matching records were returned for this query/scope, not global absence.")
    return requirements


def _exact_fact_payload(slots: AnswerSlots) -> dict[str, Any]:
    return {
        "counts": [str(value) for value in slots.counts[:8]],
        "sql_row_count": slots.sql_row_count,
        "api_item_count": slots.api_item_count,
        "names": slots.entity_names[:10],
        "ids": slots.entity_ids[:10],
        "statuses": slots.statuses[:10],
        "dates": slots.timestamps[:10],
        "first_rows": [_safe_fact_row(row) for row in slots.first_rows[:5]],
        "api_items": [_safe_fact_row(row) for row in slots.api_items[:5]],
        "important_rows": [_safe_fact_row(row) for row in slots.important_rows[:5]],
        "important_items": [_safe_fact_row(row) for row in slots.important_items[:5]],
        "caveats": {
            "dry_run": slots.dry_run,
            "api_error": slots.api_error,
            "api_evidence_state": slots.api_evidence_state,
            "live_api_evidence_available": slots.live_api_evidence_available,
        },
    }


def _safe_fact_row(row: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in row.items():
        key_text = str(key)
        key_norm = re.sub(r"[^a-z0-9]", "", key_text.lower())
        if any(token in key_norm for token in ("token", "secret", "password", "authorization", "apikey", "clientid", "clientsecret")):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key_text] = value
    return safe


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _should_try_backend_fallback(call_result: AnswerClientCallResult) -> bool:
    return not str(call_result.content or "").strip() and call_result.category in _BACKEND_FAILURE_CATEGORIES


def _try_answer_backend_fallbacks(
    primary_result: AnswerClientCallResult,
    primary_client: Any,
    question: str,
    deterministic_answer: str,
    slots: AnswerSlots,
    answer_card: Any | None,
) -> AnswerClientCallResult:
    attempts: list[dict[str, Any]] = [_attempt_summary(primary_client, primary_result, source="primary")]
    for fallback_client in _answer_backend_fallback_clients(primary_client):
        if hasattr(fallback_client, "available") and not bool(fallback_client.available()):
            attempts.append(
                {
                    "source": "fallback",
                    "client_class": type(fallback_client).__name__,
                    "llm_client_name": _client_provider_name(fallback_client),
                    "available": False,
                    "category": LLM_BACKEND_UNAVAILABLE,
                    "content_length": 0,
                }
            )
            continue
        try:
            result = _call_answer_client(fallback_client, question, deterministic_answer, slots, answer_card)
        except Exception as exc:
            attempts.append(
                {
                    "source": "fallback",
                    "client_class": type(fallback_client).__name__,
                    "llm_client_name": _client_provider_name(fallback_client),
                    "available": True,
                    "category": EXCEPTION_THROWN,
                    "exception_class": type(exc).__name__,
                    "content_length": 0,
                }
            )
            continue
        attempts.append(_attempt_summary(fallback_client, result, source="fallback"))
        if str(result.content or "").strip():
            debug = dict(result.debug)
            debug["backend_fallback_used"] = True
            debug["backend_fallback_attempts"] = attempts
            return AnswerClientCallResult(content=result.content, debug=debug, category=result.category, error=result.error)
    debug = dict(primary_result.debug)
    debug["backend_fallback_used"] = False
    debug["backend_fallback_attempts"] = attempts
    return AnswerClientCallResult(
        content=primary_result.content,
        debug=debug,
        category=primary_result.category,
        error=primary_result.error,
    )


def _answer_backend_fallback_clients(primary_client: Any) -> list[Any]:
    clients: list[Any] = []
    seen = {_client_identity(primary_client)}
    for provider in ("openai", "openai_compatible", "openrouter", "anthropic"):
        try:
            candidate = get_llm_client(provider)
        except Exception:
            continue
        identity = _client_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        clients.append(candidate)
    return clients


def _client_identity(client: Any) -> tuple[str, str | None, str | None]:
    return (type(client).__name__, _client_provider_name(client), _client_model_name(client))


def _client_provider_name(client: Any) -> str | None:
    if client is not None and hasattr(client, "provider_name"):
        try:
            return str(client.provider_name())
        except Exception:
            return type(client).__name__
    return type(client).__name__ if client is not None else None


def _client_model_name(client: Any) -> str | None:
    if client is not None and hasattr(client, "model_name"):
        try:
            return str(client.model_name())
        except Exception:
            return None
    return None


def _attempt_summary(client: Any, result: AnswerClientCallResult, *, source: str) -> dict[str, Any]:
    debug = result.debug or {}
    return {
        "source": source,
        "client_class": type(client).__name__ if client is not None else None,
        "llm_client_name": _client_provider_name(client),
        "available": debug.get("backend_available"),
        "category": result.category,
        "raw_response_error_category": debug.get("raw_response_error_category"),
        "raw_response_ok": debug.get("raw_response_ok"),
        "content_length": len(str(result.content or "")),
    }


def _normalize_answer_client_response(raw: Any, client: Any, messages: list[dict[str, Any]]) -> AnswerClientCallResult:
    content, finish_reason, malformed = _extract_answer_content(raw)
    debug = _base_debug(client, messages)
    debug.update(
        {
            "llm_request_built": True,
            "raw_response_present": raw is not None,
            "raw_response_shape": _raw_response_shape(raw),
            "extracted_content_length": len(content),
            "finish_reason": finish_reason,
            "raw_response_ok": raw.get("ok") if isinstance(raw, dict) else None,
            "raw_response_error_present": bool(raw.get("error")) if isinstance(raw, dict) else False,
            "raw_response_error_category": raw.get("error_category") if isinstance(raw, dict) else None,
        }
    )
    if content:
        return AnswerClientCallResult(content=content, debug=debug)
    if malformed:
        return AnswerClientCallResult(
            content="",
            debug=debug,
            category=CONTENT_FIELD_EXTRACTION_FAILED,
            error=CONTENT_FIELD_EXTRACTION_FAILED,
        )
    if isinstance(raw, dict) and raw.get("ok") is False and raw.get("error"):
        category = _failed_response_category(raw.get("error_category"))
        return AnswerClientCallResult(
            content="",
            debug=debug,
            category=category,
            error=category,
        )
    return AnswerClientCallResult(
        content="",
        debug=debug,
        category=LLM_RAW_RESPONSE_EMPTY,
        error=LLM_RAW_RESPONSE_EMPTY,
    )


def _extract_answer_content(raw: Any) -> tuple[str, str | None, bool]:
    malformed = False
    finish_reason = None
    candidates: list[str] = []

    def add_content(value: Any) -> None:
        nonlocal malformed
        if value is None:
            return
        if isinstance(value, str):
            candidates.append(value)
            return
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    candidates.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        candidates.append(text)
                    elif item.get("type") in {"output_text", "text"} and isinstance(item.get("value"), str):
                        candidates.append(str(item.get("value")))
                    else:
                        malformed = True
                else:
                    malformed = True
            return
        malformed = True

    if isinstance(raw, str):
        return raw.strip(), None, False
    if not isinstance(raw, dict):
        return "", None, True

    add_content(raw.get("content"))
    add_content(raw.get("output_text"))
    finish_reason = raw.get("finish_reason")

    choices = raw.get("choices")
    if choices is not None:
        if not isinstance(choices, list):
            malformed = True
        elif choices:
            first = choices[0]
            if isinstance(first, dict):
                finish_reason = first.get("finish_reason") or finish_reason
                message = first.get("message")
                if isinstance(message, dict):
                    add_content(message.get("content"))
                elif message is not None:
                    malformed = True
                add_content(first.get("text"))
            else:
                malformed = True

    output = raw.get("output")
    if output is not None:
        if not isinstance(output, list):
            malformed = True
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict):
                malformed = True
                continue
            add_content(item.get("content"))
            add_content(item.get("text"))

    content = "\n".join(piece.strip() for piece in candidates if str(piece).strip()).strip()
    return content, str(finish_reason) if finish_reason else None, malformed


def _base_debug(client: Any | None, messages: list[dict[str, Any]], *, exception: Exception | None = None) -> dict[str, Any]:
    prompt_text = "\n".join(str(message.get("content") or "") for message in messages)
    payload = {
        "llm_client_class": type(client).__name__ if client is not None else None,
        "backend_available": bool(client.available()) if client is not None and hasattr(client, "available") else client is not None,
        "llm_request_built": bool(messages),
        "request_message_count": len(messages),
        "estimated_prompt_tokens": estimate_tokens(prompt_text) if prompt_text else 0,
        "max_answer_tokens": int(os.getenv("LLM_MAX_TOKENS", "2048")),
        "raw_response_present": False,
        "raw_response_shape": {},
        "extracted_content_length": 0,
        "finish_reason": None,
        "exception_class": type(exception).__name__ if exception is not None else None,
        "exception_message": _safe_error_message(exception) if exception is not None else None,
    }
    if client is not None and hasattr(client, "provider_name"):
        try:
            payload["llm_client_name"] = str(client.provider_name())
        except Exception:
            payload["llm_client_name"] = type(client).__name__
    else:
        payload["llm_client_name"] = type(client).__name__ if client is not None else None
    return payload


def _raw_response_shape(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        shape = {
            "type": "dict",
            "keys": sorted(str(key) for key in raw.keys())[:12],
            "content_type": type(raw.get("content")).__name__ if "content" in raw else None,
            "choices_type": type(raw.get("choices")).__name__ if "choices" in raw else None,
            "output_type": type(raw.get("output")).__name__ if "output" in raw else None,
            "output_text_present": bool(raw.get("output_text")),
        }
        if isinstance(raw.get("choices"), list):
            shape["choices_count"] = len(raw.get("choices") or [])
            first = (raw.get("choices") or [{}])[0] if raw.get("choices") else {}
            shape["first_choice_keys"] = sorted(first.keys())[:8] if isinstance(first, dict) else []
        if isinstance(raw.get("output"), list):
            shape["output_count"] = len(raw.get("output") or [])
        return shape
    if isinstance(raw, str):
        return {"type": "str", "length": len(raw)}
    return {"type": type(raw).__name__}


def _safe_error_message(exc: Exception | None) -> str | None:
    if exc is None:
        return None
    redacted = redact_secrets(str(exc))
    return str(redacted)[:300]


def _failed_response_category(error_category: Any) -> str:
    if isinstance(error_category, str):
        return _FAILED_RESPONSE_CATEGORY_MAP.get(error_category, LLM_BACKEND_PROVIDER_ERROR)
    return LLM_RAW_RESPONSE_EMPTY


def _from_rewrite_result(
    result: FinalAnswerRewriteResult,
    *,
    llm_backend_used: bool,
    generator_error: str | None = None,
    generator_category: str | None = None,
    debug: dict[str, Any] | None = None,
) -> EvidenceGroundedLLMAnswerResult:
    return EvidenceGroundedLLMAnswerResult(
        final_answer=result.final_answer,
        verification=result.verification,
        first_pass_ok=result.first_pass_ok,
        rewrite_attempted=result.rewrite_attempted,
        rewrite_success=result.rewrite_success,
        fallback_used=result.fallback_used,
        llm_backend_used=llm_backend_used,
        generator_error=generator_error,
        generator_category=generator_category,
        debug=debug,
        feedback=result.feedback,
    )
