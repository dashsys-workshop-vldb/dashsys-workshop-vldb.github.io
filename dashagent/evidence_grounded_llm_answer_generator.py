from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .answer_slots import AnswerSlots
from .evidence_bus import EvidenceBus
from .evidence_grounded_final_answer_verifier import FinalAnswerRewriteResult, verify_or_rewrite_final_answer
from .llm_client import get_llm_client


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
            return _from_rewrite_result(verified, llm_backend_used=False, generator_error=f"{type(exc).__name__}: backend unavailable")
    if client is None:
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return _from_rewrite_result(verified, llm_backend_used=False)
    try:
        generated = _call_answer_client(client, question, deterministic_answer, slots, answer_card)
    except Exception as exc:
        verified = verify_or_rewrite_final_answer(
            deterministic_answer,
            deterministic_answer=deterministic_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=question,
        )
        return _from_rewrite_result(verified, llm_backend_used=False, generator_error=f"{type(exc).__name__}: answer generation failed")
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
            generator_error="EMPTY_LLM_ANSWER",
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
    return _from_rewrite_result(verified, llm_backend_used=True)


def _call_answer_client(client: Any, question: str, deterministic_answer: str, slots: AnswerSlots, answer_card: Any | None) -> str:
    payload = {
        "question": question,
        "allowed_slots": slots.compact(),
        "deterministic_answer": deterministic_answer,
        "answer_card": answer_card.to_dict() if hasattr(answer_card, "to_dict") else (answer_card if isinstance(answer_card, dict) else {}),
        "rules": [
            "Use natural wording.",
            "Use only allowed facts.",
            "Do not invent missing counts, IDs, statuses, dates, names, or relationships.",
            "API error is unavailable, not no-data.",
            "Live empty is scoped to the query only.",
        ],
    }
    messages = [
        {"role": "system", "content": "Generate a concise evidence-grounded final answer. Return answer text only."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    if hasattr(client, "complete"):
        return str(client.complete(messages)).strip()
    if hasattr(client, "chat"):
        return str(client.chat(messages)).strip()
    if hasattr(client, "complete_json"):
        return str(client.complete_json(messages).get("answer", "")).strip()
    if hasattr(client, "generate_messages"):
        result = client.generate_messages(messages)
        if isinstance(result, dict):
            return str(result.get("content") or "").strip()
    raise TypeError("unsupported evidence-grounded answer client")


def _from_rewrite_result(result: FinalAnswerRewriteResult, *, llm_backend_used: bool, generator_error: str | None = None) -> EvidenceGroundedLLMAnswerResult:
    return EvidenceGroundedLLMAnswerResult(
        final_answer=result.final_answer,
        verification=result.verification,
        first_pass_ok=result.first_pass_ok,
        rewrite_attempted=result.rewrite_attempted,
        rewrite_success=result.rewrite_success,
        fallback_used=result.fallback_used,
        llm_backend_used=llm_backend_used,
        generator_error=generator_error,
        feedback=result.feedback,
    )
