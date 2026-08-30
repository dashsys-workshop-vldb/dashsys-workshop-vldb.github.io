from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .llm_client import get_llm_client
from .post_sql_semantic_decision_gate import (
    gate_post_sql_semantic_decision,
    risk_minimizing_post_sql_fallback,
    verify_post_sql_execution_contract,
)


POST_SQL_MODES = {"CALL_API", "SKIP_API", "CAVEAT_ONLY"}
_DEFAULT_BACKEND_UNAVAILABLE_REASON: str | None = None


class PostSQLLLMBackendUnavailable(RuntimeError):
    """Raised when the default post-SQL LLM backend cannot produce a decision."""


def reset_post_sql_llm_backend_circuit_for_tests() -> None:
    global _DEFAULT_BACKEND_UNAVAILABLE_REASON
    _DEFAULT_BACKEND_UNAVAILABLE_REASON = None


def _mark_default_backend_unavailable(reason: str) -> None:
    global _DEFAULT_BACKEND_UNAVAILABLE_REASON
    _DEFAULT_BACKEND_UNAVAILABLE_REASON = reason[:200] if reason else "backend unavailable"


@dataclass(frozen=True)
class PostSQLLLMDecision:
    mode: str
    endpoint_id: str | None = None
    confidence: float = 0.0
    codes: list[str] = field(default_factory=list)
    source: str = "LLM_POST_SQL_DECISION"
    llm_call_attempted: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 4)
        return payload


def parse_post_sql_llm_decision(raw: str | dict[str, Any]) -> PostSQLLLMDecision:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    mode = str(payload.get("mode") or "CAVEAT_ONLY").upper()
    if mode not in POST_SQL_MODES:
        mode = "CAVEAT_ONLY"
    confidence = payload.get("confidence", payload.get("conf", 0.0))
    codes = payload.get("codes") if isinstance(payload.get("codes"), list) else []
    endpoint_id = payload.get("endpoint_id")
    return PostSQLLLMDecision(
        mode=mode,
        endpoint_id=str(endpoint_id) if endpoint_id else None,
        confidence=max(0.0, min(1.0, float(confidence or 0.0))),
        codes=[str(code) for code in codes][:8],
        source=str(payload.get("source") or "LLM_POST_SQL_DECISION"),
        llm_call_attempted=True,
    )


def run_post_sql_llm_first_decision(
    card: dict[str, Any],
    *,
    llm_client: Any | None = None,
    enabled: bool = True,
    budget_available: bool = True,
) -> dict[str, Any]:
    explicit_client = llm_client is not None
    client = _client(llm_client) if enabled else None
    if client is None:
        fallback = risk_minimizing_post_sql_fallback(card)
        verified = verify_post_sql_execution_contract(
            fallback,
            card,
            budget_available=budget_available,
            source=fallback.fallback_source,
        )
        return {
            "enabled": enabled,
            "llm_backend_available": False,
            "first_decision": None,
            "first_pass_ok": False,
            "revision_attempted": False,
            "revision_success": False,
            "feedback": None,
            "second_decision": None,
            "fallback": fallback.to_dict(),
            "execution_verifier": verified.to_dict(),
            "metrics": _metrics(first_fail=True, revision_attempted=False, revision_success=False, fallback=fallback),
        }

    try:
        first = _call_decision_client(client, _messages_for_card(card))
    except Exception as exc:
        if not explicit_client:
            _mark_default_backend_unavailable(str(exc))
        fallback = risk_minimizing_post_sql_fallback(card)
        verified = verify_post_sql_execution_contract(
            fallback,
            card,
            budget_available=budget_available,
            source=fallback.fallback_source,
        )
        return {
            "enabled": True,
            "llm_backend_available": False,
            "llm_error": f"{type(exc).__name__}: backend unavailable",
            "first_decision": None,
            "first_pass_ok": False,
            "revision_attempted": False,
            "revision_success": False,
            "feedback": None,
            "second_decision": None,
            "fallback": fallback.to_dict(),
            "execution_verifier": verified.to_dict(),
            "metrics": _metrics(first_fail=True, revision_attempted=False, revision_success=False, fallback=fallback),
        }
    gate1 = gate_post_sql_semantic_decision(first, card)
    if gate1.ok:
        verified = verify_post_sql_execution_contract(first, card, budget_available=budget_available, source="LLM_DECISION_VERIFIED")
        return {
            "enabled": True,
            "llm_backend_available": True,
            "first_decision": first.to_dict(),
            "first_gate": gate1.to_dict(),
            "first_pass_ok": True,
            "revision_attempted": False,
            "revision_success": False,
            "feedback": None,
            "second_decision": None,
            "fallback": None,
            "execution_verifier": verified.to_dict(),
            "metrics": _metrics(first_fail=False, revision_attempted=False, revision_success=False, fallback=None),
        }

    feedback = gate1.feedback
    second: PostSQLLLMDecision | None = None
    gate2 = None
    if feedback is not None:
        try:
            second = _call_decision_client(client, _messages_for_feedback(feedback.to_dict()))
        except Exception:
            second = None
            gate2 = None
        if second is not None:
            gate2 = gate_post_sql_semantic_decision(second, card)
            if gate2.ok:
                verified = verify_post_sql_execution_contract(second, card, budget_available=budget_available, source="LLM_DECISION_VERIFIED")
                return {
                    "enabled": True,
                    "llm_backend_available": True,
                    "first_decision": first.to_dict(),
                    "first_gate": gate1.to_dict(),
                    "first_pass_ok": False,
                    "revision_attempted": True,
                    "revision_success": True,
                    "feedback": feedback.to_dict(),
                    "second_decision": second.to_dict(),
                    "second_gate": gate2.to_dict(),
                    "fallback": None,
                    "execution_verifier": verified.to_dict(),
                    "metrics": _metrics(first_fail=True, revision_attempted=True, revision_success=True, fallback=None, feedback=feedback.to_dict()),
                }

    fallback = risk_minimizing_post_sql_fallback(card)
    verified = verify_post_sql_execution_contract(
        fallback,
        card,
        budget_available=budget_available,
        source=fallback.fallback_source,
    )
    return {
        "enabled": True,
        "llm_backend_available": True,
        "first_decision": first.to_dict(),
        "first_gate": gate1.to_dict(),
        "first_pass_ok": False,
        "revision_attempted": feedback is not None,
        "revision_success": False,
        "feedback": feedback.to_dict() if feedback else None,
        "second_decision": second.to_dict() if second else None,
        "second_gate": gate2.to_dict() if gate2 else None,
        "fallback": fallback.to_dict(),
        "execution_verifier": verified.to_dict(),
        "metrics": _metrics(first_fail=True, revision_attempted=feedback is not None, revision_success=False, fallback=fallback, feedback=feedback.to_dict() if feedback else None),
    }


def _messages_for_card(card: dict[str, Any]) -> list[dict[str, str]]:
    schema = {
        "mode": "CALL_API|SKIP_API|CAVEAT_ONLY",
        "endpoint_id": "allowed endpoint id or null",
        "confidence": "0.0-1.0",
        "codes": ["short codes"],
    }
    return [
        {
            "role": "system",
            "content": "Decide post-SQL API action. Return JSON only. Do not answer the user, write SQL, API params, endpoint paths, or prose.",
        },
        {"role": "user", "content": json.dumps({"card": card, "schema": schema}, sort_keys=True)},
    ]


def _messages_for_feedback(feedback: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Revise the post-SQL API decision from compact verifier feedback. Return JSON only.",
        },
        {"role": "user", "content": json.dumps(feedback, sort_keys=True)},
    ]


def _call_decision_client(client: Any, messages: list[dict[str, str]]) -> PostSQLLLMDecision:
    raw = _call_client(client, messages)
    return parse_post_sql_llm_decision(raw)


def _call_client(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "generate_messages"):
        result = client.generate_messages(messages)
        if isinstance(result, dict) and result.get("ok") and result.get("content"):
            return str(result.get("content") or "")
        if isinstance(result, dict):
            reason = str(result.get("error") or result.get("reason") or "post-sql LLM returned no content")
            if result.get("skipped") or not result.get("ok"):
                raise PostSQLLLMBackendUnavailable(reason)
            raise RuntimeError(reason)
        raise RuntimeError("post-sql LLM returned unsupported SDK response")
    if hasattr(client, "complete"):
        return str(client.complete(messages))
    if hasattr(client, "chat"):
        return str(client.chat(messages))
    if hasattr(client, "complete_json"):
        return json.dumps(client.complete_json(messages), sort_keys=True)
    raise TypeError("unsupported post-sql LLM decision client")


def _client(llm_client: Any | None) -> Any | None:
    if llm_client is not None:
        return llm_client
    if _DEFAULT_BACKEND_UNAVAILABLE_REASON:
        return None
    try:
        client = get_llm_client()
    except Exception:
        return None
    if hasattr(client, "available") and not client.available():
        _mark_default_backend_unavailable(getattr(client, "reason", "LLM provider is unavailable"))
        return None
    return client


def _metrics(
    *,
    first_fail: bool,
    revision_attempted: bool,
    revision_success: bool,
    fallback: Any | None,
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = None
    if fallback is not None:
        source = fallback.fallback_source if hasattr(fallback, "fallback_source") else dict(fallback).get("fallback_source")
    return {
        "first_pass_fail_count": 1 if first_fail else 0,
        "revision_attempt_count": 1 if revision_attempted else 0,
        "revision_success_count": 1 if revision_success else 0,
        "revision_fail_count": 1 if revision_attempted and not revision_success else 0,
        "fallback_count": 1 if fallback is not None else 0,
        "post_sql_first_pass_fail_count": 1 if first_fail else 0,
        "post_sql_revision_attempt_count": 1 if revision_attempted else 0,
        "post_sql_revision_success_count": 1 if revision_success else 0,
        "post_sql_revision_fail_count": 1 if revision_attempted and not revision_success else 0,
        "post_sql_risk_fallback_count": 1 if fallback is not None else 0,
        "fallback_source_counts": {source: 1} if source else {},
        "average_feedback_token_estimate": max(0, len(str(feedback or {})) // 4),
    }
