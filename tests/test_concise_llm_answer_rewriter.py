from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.concise_llm_answer_rewriter import rewrite_concise_answer
from dashagent.concise_rewrite_card import build_concise_rewrite_card
from dashagent.concise_rewrite_eligibility import decide_concise_rewrite_eligibility


class FakeClient:
    def __init__(self, response) -> None:
        self.response = response

    def available(self) -> bool:
        return True

    def complete(self, messages, **kwargs):
        self.messages = messages
        self.kwargs = kwargs
        return self.response


class FailingClient:
    def available(self) -> bool:
        return True

    def complete(self, messages, **kwargs):
        raise RuntimeError("backend unavailable")


def _slots(query: str, **overrides) -> AnswerSlots:
    slots = AnswerSlots(query=query, answer_family=overrides.pop("answer_family", "unit"))
    for key, value in overrides.items():
        setattr(slots, key, value)
    return slots


def _card(prompt: str, legacy: str, slots: AnswerSlots):
    decision = decide_concise_rewrite_eligibility(prompt=prompt, legacy_answer=legacy, slots=slots)
    return build_concise_rewrite_card(prompt=prompt, legacy_answer=legacy, slots=slots, eligibility=decision)


def test_non_empty_fake_llm_response_returns_rewrite() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], evidence_numbers={"74"})
    card = _card(slots.query, "The local snapshot contains 74 schema records.", slots)

    result = rewrite_concise_answer(card, llm_client=FakeClient("You have 74 schemas."))

    assert result.rewritten_answer == "You have 74 schemas."
    assert result.category == "ok"
    assert result.backend_available is True
    assert result.extracted_content_length > 0


def test_openai_choices_message_content_shape_is_parsed() -> None:
    slots = _slots("When was Birthday Message published?", entity_names=["Birthday Message"], timestamps=["2026-03-31"])
    card = _card(slots.query, "Birthday Message has published_time 2026-03-31.", slots)
    raw = {"choices": [{"message": {"content": "Birthday Message was published on 2026-03-31."}}]}

    result = rewrite_concise_answer(card, llm_client=FakeClient(raw))

    assert result.rewritten_answer == "Birthday Message was published on 2026-03-31."


def test_output_text_shape_is_parsed() -> None:
    slots = _slots("What is Journey A status?", entity_names=["Journey A"], statuses=["inactive"])
    card = _card(slots.query, "Journey A has status inactive.", slots)

    result = rewrite_concise_answer(card, llm_client=FakeClient({"output_text": "Journey A is inactive."}))

    assert result.rewritten_answer == "Journey A is inactive."


def test_empty_response_is_classified_and_keeps_no_answer() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    card = _card(slots.query, "The local snapshot contains 74 schema records.", slots)

    result = rewrite_concise_answer(card, llm_client=FakeClient("   "))

    assert result.rewritten_answer == ""
    assert result.category == "empty_rewrite"


def test_backend_unavailable_is_classified_separately() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    card = _card(slots.query, "The local snapshot contains 74 schema records.", slots)

    result = rewrite_concise_answer(card, llm_client=FailingClient())

    assert result.rewritten_answer == ""
    assert result.category == "backend_unavailable"
    assert result.exception_class == "RuntimeError"
