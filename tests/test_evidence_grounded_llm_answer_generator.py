from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.evidence_grounded_llm_answer_generator import generate_evidence_grounded_llm_answer


class FakeAnswerClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, messages):
        return self.answer


def _slots() -> AnswerSlots:
    return AnswerSlots(
        query="Show schema status",
        answer_family="status",
        entity_names=["Profile Schema"],
        entity_ids=["schema-123"],
        statuses=["active"],
        first_rows=[{"id": "schema-123", "name": "Profile Schema", "status": "active"}],
        evidence_strings={"profile schema", "schema-123", "active"},
    )


def test_llm_answer_generator_accepts_free_wording_when_grounded() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("Profile Schema is active."),
    )

    assert result.final_answer == "Profile Schema is active."
    assert result.verification.ok is True
    assert result.fallback_used is False


def test_llm_answer_generator_falls_back_when_answer_overreaches() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("Profile Schema is inactive."),
    )

    assert result.final_answer == "Status: {id=schema-123, name=Profile Schema, status=active}."
    assert result.fallback_used is True


def test_llm_answer_generator_falls_back_when_answer_empty() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("   "),
    )

    assert result.final_answer == "Status: {id=schema-123, name=Profile Schema, status=active}."
    assert result.fallback_used is True
    assert result.generator_error == "EMPTY_LLM_ANSWER"
