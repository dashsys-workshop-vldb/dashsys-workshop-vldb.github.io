from __future__ import annotations

from dashagent.answer_intent_router import route_answer_intent
from dashagent.answer_slots import AnswerSlots


def _slots(query: str, **kwargs) -> AnswerSlots:
    defaults = {"query": query, "answer_family": "journey_campaign"}
    defaults.update(kwargs)
    return AnswerSlots(**defaults)


def test_count_prompt_with_count_slot_routes_to_canonical_count() -> None:
    slots = _slots("How many schema records are in the local snapshot?", counts=[2], sql_row_count=1)

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "COUNT"
    assert decision.answer_mode == "CANONICAL_DATA"
    assert decision.confidence == "HIGH"


def test_list_prompt_with_list_slots_routes_to_canonical_list() -> None:
    slots = _slots("List inactive journeys.", entity_names=["Birthday Message", "Welcome Journey"])

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "LIST"
    assert decision.answer_mode == "CANONICAL_DATA"


def test_status_prompt_with_status_slot_routes_to_canonical_status() -> None:
    slots = _slots("Show Birthday Message status.", entity_names=["Birthday Message"], statuses=["draft"])

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "STATUS"
    assert decision.answer_mode == "CANONICAL_DATA"


def test_date_prompt_with_timestamp_slot_routes_to_canonical_date() -> None:
    slots = _slots("When was Birthday Message published?", entity_names=["Birthday Message"], timestamps=["2026-03-31T06:07:32Z"])

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "DATE"
    assert decision.answer_mode == "CANONICAL_DATA"


def test_conceptual_prompt_without_data_routes_to_llm_concept() -> None:
    slots = _slots("What is a schema?")

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "CONCEPT"
    assert decision.answer_mode == "LLM_CONCEPT"


def test_mixed_concept_and_data_prompt_routes_to_hybrid() -> None:
    slots = _slots(
        "Explain what inactive journey means and show inactive journeys.",
        entity_names=["Birthday Message"],
        statuses=["draft"],
        first_rows=[{"name": "Birthday Message", "status": "draft"}],
    )

    decision = route_answer_intent(slots.query, slots=slots)

    assert decision.answer_intent == "MIXED"
    assert decision.answer_mode == "HYBRID_MIXED"


def test_api_error_primary_routes_to_canonical_caveat() -> None:
    slots = _slots("Show current schemas.", api_error=True, answer_slot_source="api_error")

    decision = route_answer_intent(slots.query, slots=slots, evidence_quality={"api": ["API_ERROR"]})

    assert decision.answer_intent == "ERROR_CAVEAT"
    assert decision.answer_mode == "CANONICAL_CAVEAT"

