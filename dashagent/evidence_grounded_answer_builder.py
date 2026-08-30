from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .answer_slot_renderer import RenderedAnswer, render_answer_slots
from .answer_slots import AnswerSlots, extract_answer_slots
from .evidence_quality_classifier import classify_evidence_quality


@dataclass(frozen=True)
class EvidenceGroundedAnswer:
    answer: str
    renderer: dict[str, Any]
    evidence_quality: dict[str, Any]
    unsupported_claims_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_grounded_answer(
    query: str,
    tool_results: list[dict[str, Any]],
    *,
    slots: AnswerSlots | None = None,
    evidence_quality: dict[str, Any] | None = None,
    api_required: bool = False,
) -> EvidenceGroundedAnswer:
    final_slots = slots or extract_answer_slots(query, tool_results)
    quality = evidence_quality or classify_evidence_quality(tool_results, api_required=api_required)
    rendered: RenderedAnswer = render_answer_slots(query, final_slots, quality)
    return EvidenceGroundedAnswer(
        answer=rendered.answer,
        renderer=rendered.to_dict(),
        evidence_quality=quality,
        unsupported_claims_count=rendered.unsupported_claims_count,
    )
