from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_intent_router import AnswerIntentDecision, route_answer_intent
from .answer_slots import AnswerSlots
from .evidence_grounded_final_answer_verifier import EvidenceGroundedFinalAnswerVerification, verify_evidence_grounded_final_answer
from .canonical_data_renderer import CanonicalAnswer, render_canonical_data_answer
from .hybrid_mixed_answer_composer import HybridMixedAnswer, compose_hybrid_mixed_answer
from .llm_concept_answer_generator import LLMConceptAnswerResult, generate_llm_concept_answer
from .answer_candidate_selector import select_answer_candidate


@dataclass(frozen=True)
class HybridAnswerResult:
    final_answer: str
    selected_source: str
    intent: AnswerIntentDecision
    verification: EvidenceGroundedFinalAnswerVerification
    fallback_used: bool = False
    selection_codes: list[str] = field(default_factory=list)
    canonical: CanonicalAnswer | None = None
    concept: LLMConceptAnswerResult | None = None
    mixed: HybridMixedAnswer | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "selected_source": self.selected_source,
            "answer_intent": self.intent.to_dict(),
            "verification": self.verification.to_dict(),
            "fallback_used": self.fallback_used,
            "selection_codes": self.selection_codes,
            "canonical": self.canonical.to_dict() if self.canonical is not None else None,
            "concept": self.concept.to_dict() if self.concept is not None else None,
            "mixed": self.mixed.to_dict() if self.mixed is not None else None,
        }


def compose_hybrid_answer(
    prompt: str,
    *,
    slots: AnswerSlots,
    evidence_bus: Any | None = None,
    evidence_quality: dict[str, Any] | None = None,
    answer_card: Any | None = None,
    legacy_answer: str = "",
    llm_client: Any | None = None,
) -> HybridAnswerResult:
    intent = route_answer_intent(prompt, slots=slots, evidence_bus=evidence_bus, evidence_quality=evidence_quality)
    if intent.answer_mode in {"CANONICAL_DATA", "CANONICAL_DATA_SELECTIVE", "LEGACY_FIRST_DATA"}:
        canonical = render_canonical_data_answer(prompt, intent, slots, evidence_quality=evidence_quality, evidence_bus=evidence_bus)
        canonical_verification = verify_evidence_grounded_final_answer(
            canonical.answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=prompt,
        )
        selection = select_answer_candidate(
            prompt=prompt,
            slots=slots,
            evidence_bus=evidence_bus,
            hybrid_answer=canonical.answer,
            hybrid_verification=canonical_verification,
            legacy_answer=legacy_answer,
            grounded_answer=canonical.answer,
        )
        verification = verify_evidence_grounded_final_answer(
            selection.selected_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=prompt,
        )
        selected_source = "HYBRID_CANONICAL_DATA" if selection.selected_source == "HYBRID_ANSWER" else selection.selected_source
        return HybridAnswerResult(
            final_answer=selection.selected_answer,
            selected_source=selected_source,
            intent=intent,
            verification=verification,
            fallback_used=selection.selected_source != "HYBRID_ANSWER",
            selection_codes=selection.selection_codes,
            canonical=canonical,
        )
    if intent.answer_mode == "CANONICAL_CAVEAT":
        canonical = render_canonical_data_answer(prompt, intent, slots, evidence_quality=evidence_quality, evidence_bus=evidence_bus)
        return _verified_or_legacy(
            prompt,
            candidate=canonical.answer,
            source="HYBRID_CANONICAL_CAVEAT",
            intent=intent,
            slots=slots,
            evidence_bus=evidence_bus,
            answer_card=answer_card,
            legacy_answer=legacy_answer,
            selection_codes=["SELECT_HYBRID_CANONICAL_CAVEAT"],
            canonical=canonical,
            require_roles=canonical.rendered_roles,
        )
    if intent.answer_mode == "LLM_CONCEPT":
        concept = generate_llm_concept_answer(prompt, slots=slots, evidence_bus=evidence_bus, llm_client=llm_client)
        return _verified_or_legacy(
            prompt,
            candidate=concept.answer,
            source="HYBRID_LLM_CONCEPT",
            intent=intent,
            slots=slots,
            evidence_bus=evidence_bus,
            answer_card=answer_card,
            legacy_answer=legacy_answer,
            selection_codes=["SELECT_HYBRID_LLM_CONCEPT"],
            concept=concept,
        )
    if intent.answer_mode == "HYBRID_MIXED":
        mixed = compose_hybrid_mixed_answer(
            prompt,
            slots=slots,
            intent=intent,
            evidence_quality=evidence_quality,
            evidence_bus=evidence_bus,
            llm_client=llm_client,
        )
        return _verified_or_legacy(
            prompt,
            candidate=mixed.answer,
            source="HYBRID_MIXED",
            intent=intent,
            slots=slots,
            evidence_bus=evidence_bus,
            answer_card=answer_card,
            legacy_answer=legacy_answer,
            selection_codes=["SELECT_HYBRID_MIXED"],
            concept=mixed.concept,
            canonical=mixed.data,
            mixed=mixed,
            require_roles=mixed.data.rendered_roles,
        )
    fallback_verification = verify_evidence_grounded_final_answer(legacy_answer, answer_card=answer_card, slots=slots, evidence_bus=evidence_bus, question=prompt)
    return HybridAnswerResult(
        final_answer=legacy_answer,
        selected_source="LEGACY_SAFE_RENDERER",
        intent=intent,
        verification=fallback_verification,
        fallback_used=True,
        selection_codes=["SELECT_LEGACY_UNKNOWN_INTENT"],
    )


def _verified_or_legacy(
    prompt: str,
    *,
    candidate: str,
    source: str,
    intent: AnswerIntentDecision,
    slots: AnswerSlots,
    evidence_bus: Any | None,
    answer_card: Any | None,
    legacy_answer: str,
    selection_codes: list[str],
    canonical: CanonicalAnswer | None = None,
    concept: LLMConceptAnswerResult | None = None,
    mixed: HybridMixedAnswer | None = None,
    require_roles: list[str] | None = None,
) -> HybridAnswerResult:
    if not str(candidate or "").strip():
        return _legacy(prompt, intent, slots, evidence_bus, answer_card, legacy_answer, ["SELECT_LEGACY_MISSING_SLOTS"], canonical, concept, mixed)
    verification = verify_evidence_grounded_final_answer(candidate, answer_card=answer_card, slots=slots, evidence_bus=evidence_bus, question=prompt)
    if verification.ok and _roles_rendered(candidate, require_roles or [], prompt=prompt, slots=slots):
        if source == "HYBRID_CANONICAL_DATA" and _legacy_data_answer_preferred(prompt, candidate, legacy_answer, slots):
            return _legacy(
                prompt,
                intent,
                slots,
                evidence_bus,
                answer_card,
                legacy_answer,
                ["SELECT_LEGACY_HYBRID_NOT_BETTER_THAN_LEGACY"],
                canonical,
                concept,
                mixed,
            )
        return HybridAnswerResult(
            final_answer=candidate,
            selected_source=source,
            intent=intent,
            verification=verification,
            fallback_used=False,
            selection_codes=selection_codes,
            canonical=canonical,
            concept=concept,
            mixed=mixed,
        )
    codes = ["SELECT_LEGACY_HYBRID_UNSUPPORTED"] if not verification.ok else ["SELECT_LEGACY_MISSING_SLOTS"]
    return _legacy(prompt, intent, slots, evidence_bus, answer_card, legacy_answer, codes, canonical, concept, mixed)


def _legacy(
    prompt: str,
    intent: AnswerIntentDecision,
    slots: AnswerSlots,
    evidence_bus: Any | None,
    answer_card: Any | None,
    legacy_answer: str,
    codes: list[str],
    canonical: CanonicalAnswer | None = None,
    concept: LLMConceptAnswerResult | None = None,
    mixed: HybridMixedAnswer | None = None,
) -> HybridAnswerResult:
    verification = verify_evidence_grounded_final_answer(legacy_answer, answer_card=answer_card, slots=slots, evidence_bus=evidence_bus, question=prompt)
    grounded_answer = str(getattr(answer_card, "answer", "") or "")
    if not verification.ok and grounded_answer.strip() and grounded_answer.strip() != str(legacy_answer or "").strip():
        grounded_verification = verify_evidence_grounded_final_answer(
            grounded_answer,
            answer_card=answer_card,
            slots=slots,
            evidence_bus=evidence_bus,
            question=prompt,
        )
        if grounded_verification.ok:
            return HybridAnswerResult(
                final_answer=grounded_answer,
                selected_source="DETERMINISTIC_FALLBACK",
                intent=intent,
                verification=grounded_verification,
                fallback_used=True,
                selection_codes=[*codes, "SELECT_DETERMINISTIC_FALLBACK_LEGACY_UNSUPPORTED"],
                canonical=canonical,
                concept=concept,
                mixed=mixed,
            )
    return HybridAnswerResult(
        final_answer=legacy_answer,
        selected_source="LEGACY_SAFE_RENDERER",
        intent=intent,
        verification=verification,
        fallback_used=True,
        selection_codes=codes,
        canonical=canonical,
        concept=concept,
        mixed=mixed,
    )


def _roles_rendered(candidate: str, roles: list[str], *, prompt: str, slots: AnswerSlots) -> bool:
    if not roles:
        roles = []
    text = candidate.strip()
    lowered = text.lower()
    prompt_l = prompt.lower()
    if ("COUNT" in roles or any(token in prompt_l for token in ("how many", "count", "total", "number of"))) and not any(ch.isdigit() for ch in text):
        return False
    if any(token in prompt_l for token in ("id", "ids", "identifier", "details", "all columns", "including all columns")) and slots.entity_ids:
        if not any(str(value).lower() in lowered for value in slots.entity_ids[:5]):
            return False
    if any(token in prompt_l for token in ("list", "show", "return", "give me", "which", "export", "details")) and slots.entity_names:
        if not any(str(value).lower() in lowered for value in slots.entity_names[:5]):
            return False
    if any(token in prompt_l for token in ("when", "created", "updated", "modified", "published", "date")) and slots.timestamps:
        date_values = [str(value)[:10].lower() for value in slots.timestamps[:5] if str(value)]
        if date_values and not any(value in lowered for value in date_values):
            return False
    quoted = _quoted_prompt_values(prompt)
    if quoted and any(token in prompt_l for token in ("named", "called", "details", "show me the details", "for ")):
        if not any(value.lower() in lowered for value in quoted) and "did not return" not in lowered:
            return False
    return True


def _quoted_prompt_values(prompt: str) -> list[str]:
    import re

    values: list[str] = []
    for match in re.findall(r"'([^']+)'|\"([^\"]+)\"", prompt):
        value = (match[0] or match[1]).strip()
        if value:
            values.append(value)
    return values


def _legacy_data_answer_preferred(prompt: str, candidate: str, legacy_answer: str, slots: AnswerSlots) -> bool:
    if not str(legacy_answer or "").strip():
        return False
    if "local snapshot" in prompt.lower() and any(token in prompt.lower() for token in ("how many", "count", "total", "number of")):
        return False
    if _weak_legacy_answer(legacy_answer) and _runtime_fact_coverage(candidate, slots) > 0:
        return False
    return _runtime_fact_coverage(candidate, slots) <= _runtime_fact_coverage(legacy_answer, slots)


def _weak_legacy_answer(answer: str) -> bool:
    lowered = answer.lower()
    weak_phrases = (
        "no data available",
        "did not provide usable data",
        "no matching evidence",
        "sql query returned zero rows",
        "there are no",
        "unable to answer",
    )
    return any(phrase in lowered for phrase in weak_phrases)


def _runtime_fact_coverage(answer: str, slots: AnswerSlots) -> int:
    lowered = answer.lower()
    score = 0
    for value in slots.counts[:6]:
        text = str(value)
        if text and text.lower() in lowered:
            score += 3
    for value in slots.entity_names[:8]:
        if str(value).lower() in lowered:
            score += 2
    for value in slots.entity_ids[:8]:
        if str(value).lower() in lowered:
            score += 2
    for value in slots.statuses[:8]:
        if str(value).lower() in lowered:
            score += 1
    for value in slots.timestamps[:8]:
        date = str(value)[:10].lower()
        if date and date in lowered:
            score += 2
    if (slots.api_error or slots.dry_run) and any(token in lowered for token in ("api unavailable", "cannot verify", "not executed")):
        score += 1
    return score
