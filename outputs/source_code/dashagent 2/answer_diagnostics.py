from __future__ import annotations

from typing import Any

from .answer_intent import AnswerIntent
from .answer_slots import AnswerSlots
from .answer_verifier import VerificationResult


def build_answer_diagnostics(
    *,
    slots: AnswerSlots,
    intent: AnswerIntent,
    verification: VerificationResult,
    completeness_missing_fields: list[str] | None = None,
    rewrite_applied: bool = False,
    selected_candidate_type: str = "base",
) -> dict[str, Any]:
    return {
        "answer_family": slots.answer_family,
        "answer_intent": intent.value if hasattr(intent, "value") else str(intent),
        "slots_present": slots.slots_present(),
        "verifier_passed": verification.ok,
        "unsupported_claims_count": verification.unsupported_count,
        "completeness_missing_fields": (completeness_missing_fields or [])[:5],
        "rewrite_applied": rewrite_applied,
        "selected_candidate_type": selected_candidate_type,
    }
