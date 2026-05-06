from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .answer_diagnostics import build_answer_diagnostics
from .answer_intent import AnswerIntent, classify_answer_intent, intent_matches_answer
from .answer_slots import AnswerSlots, extract_answer_slots
from .answer_verifier import VerificationResult, safe_rewrite, verify_answer


@dataclass
class AnswerCandidate:
    candidate_type: str
    text: str
    verification: VerificationResult
    intent_match: bool
    completeness_missing_fields: list[str]
    score: float


@dataclass
class AnswerSelection:
    answer: str
    diagnostics: dict[str, Any]
    candidate: AnswerCandidate
    slots: AnswerSlots
    intent: AnswerIntent


def select_best_answer(
    query: str,
    tool_results: list[dict[str, Any]],
    base_answer: str,
    *,
    slots: AnswerSlots | None = None,
    intent: AnswerIntent | None = None,
) -> AnswerSelection:
    answer_slots = slots or extract_answer_slots(query, tool_results)
    answer_intent = intent or classify_answer_intent(query, answer_slots)
    candidates = build_candidates(query, answer_slots, answer_intent, base_answer)
    ranked = sorted(candidates, key=lambda candidate: (candidate.score, -len(candidate.text)), reverse=True)
    selected = ranked[0]
    diagnostics = build_answer_diagnostics(
        slots=answer_slots,
        intent=answer_intent,
        verification=selected.verification,
        completeness_missing_fields=selected.completeness_missing_fields,
        rewrite_applied=selected.candidate_type != "base",
        selected_candidate_type=selected.candidate_type,
    )
    return AnswerSelection(
        answer=selected.text,
        diagnostics=diagnostics,
        candidate=selected,
        slots=answer_slots,
        intent=answer_intent,
    )


def build_candidates(
    query: str,
    slots: AnswerSlots,
    intent: AnswerIntent,
    base_answer: str,
) -> list[AnswerCandidate]:
    raw_candidates = [
        ("base", base_answer),
        ("safe_rewrite", safe_rewrite(query, slots, intent, slots.answer_family)),
        ("evidence_grounded", evidence_grounded_candidate(query, slots, intent)),
    ]
    seen: set[str] = set()
    candidates: list[AnswerCandidate] = []
    for candidate_type, text in raw_candidates:
        normalized = " ".join(text.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        verification = verify_answer(normalized, slots)
        missing = completeness_missing_fields(intent, slots, normalized)
        match = intent_matches_answer(normalized, intent)
        score = score_candidate(candidate_type, normalized, verification, match, missing)
        candidates.append(
            AnswerCandidate(
                candidate_type=candidate_type,
                text=normalized,
                verification=verification,
                intent_match=match,
                completeness_missing_fields=missing,
                score=score,
            )
        )
    if not candidates:
        fallback = safe_rewrite(query, slots, intent, slots.answer_family)
        verification = verify_answer(fallback, slots)
        candidates.append(
            AnswerCandidate(
                candidate_type="safe_rewrite",
                text=fallback,
                verification=verification,
                intent_match=intent_matches_answer(fallback, intent),
                completeness_missing_fields=completeness_missing_fields(intent, slots, fallback),
                score=0.0,
            )
        )
    return candidates


def score_candidate(
    candidate_type: str,
    text: str,
    verification: VerificationResult,
    intent_match: bool,
    missing: list[str],
) -> float:
    score = 0.0
    if verification.ok:
        score += 100.0
    else:
        score -= 12.0 * max(1, verification.unsupported_count)
        score -= 4.0 * len(verification.errors)
    if intent_match:
        score += 2.0
    score -= 4.0 * len(missing)
    if candidate_type == "base" and verification.ok:
        score += 20.0
    if "live API verification was not executed because Adobe credentials are unavailable" in text:
        score += 1.0
    score -= min(len(text) / 2000.0, 1.0)
    return score


def completeness_missing_fields(intent: AnswerIntent, slots: AnswerSlots, answer: str) -> list[str]:
    lowered = answer.lower()
    missing: list[str] = []
    if intent == AnswerIntent.COUNT and not any(token in lowered for token in ["count", "there are", "there is"]):
        missing.append("count_shape")
    if intent == AnswerIntent.LIST and not (slots.entity_names or slots.entity_ids or "requires live api" in lowered or "no " in lowered):
        missing.append("list_items")
    if intent == AnswerIntent.WHEN and not (slots.timestamps or slots.date_ranges or "requires live api" in lowered):
        missing.append("timestamp")
    if intent == AnswerIntent.STATUS and not (slots.statuses or "status" in lowered or "state" in lowered or "requires live api" in lowered):
        missing.append("status")
    if slots.dry_run and "live api verification was not executed" not in lowered:
        missing.append("dry_run_caveat")
    if slots.discrepancy and not any(token in lowered for token in ["disagree", "discrepancy", "does not match"]):
        missing.append("discrepancy")
    return missing


def evidence_grounded_candidate(query: str, slots: AnswerSlots, intent: AnswerIntent) -> str:
    safe = safe_rewrite(query, slots, intent, slots.answer_family)
    if safe.startswith("Based on") or safe.startswith("The "):
        return safe
    return f"Based on the available evidence, {safe[0].lower() + safe[1:] if safe else safe}"
