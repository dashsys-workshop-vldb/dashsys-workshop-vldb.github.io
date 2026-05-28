from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .answer_slots import AnswerSlots
from .canonical_data_renderer import CanonicalAnswer, render_canonical_data_answer
from .llm_concept_answer_generator import LLMConceptAnswerResult, generate_llm_concept_answer
from .answer_intent_router import AnswerIntentDecision


@dataclass(frozen=True)
class HybridMixedAnswer:
    answer: str
    concept: LLMConceptAnswerResult
    data: CanonicalAnswer

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.answer, "concept": self.concept.to_dict(), "data": self.data.to_dict()}


def compose_hybrid_mixed_answer(
    prompt: str,
    *,
    slots: AnswerSlots,
    intent: AnswerIntentDecision,
    evidence_quality: dict[str, Any] | None = None,
    evidence_bus: Any | None = None,
    llm_client: Any | None = None,
) -> HybridMixedAnswer:
    concept = generate_llm_concept_answer(prompt, slots=slots, evidence_bus=evidence_bus, llm_client=llm_client)
    data_intent = _data_intent_for_mixed(prompt, slots)
    data = render_canonical_data_answer(
        prompt,
        AnswerIntentDecision(data_intent, "CANONICAL_DATA", intent.confidence, ["MIXED_DATA_SECTION"]),
        slots,
        evidence_quality=evidence_quality,
        evidence_bus=evidence_bus,
    )
    concept_sentence = concept.answer.strip()
    if concept_sentence and concept_sentence[-1] not in ".!?":
        concept_sentence = f"{concept_sentence}."
    answer = " ".join(part.strip() for part in [concept_sentence, data.answer] if part and part.strip())
    return HybridMixedAnswer(answer.strip(), concept, data)


def _data_intent_for_mixed(prompt: str, slots: AnswerSlots) -> str:
    lowered = prompt.lower()
    if any(token in lowered for token in ("how many", "count", "total", "number of")) and slots.counts:
        return "COUNT"
    if any(token in lowered for token in ("when", "created", "updated", "published", "date")) and slots.timestamps:
        return "DATE"
    if any(token in lowered for token in ("status", "active", "inactive", "failed", "published")) and (slots.statuses or slots.first_rows or slots.important_rows):
        return "STATUS"
    if any(token in lowered for token in ("connected", "associated", "relationship")):
        return "RELATIONSHIP"
    return "LIST"
