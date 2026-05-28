from __future__ import annotations

from dashagent.answer_intent_router import AnswerIntentDecision
from dashagent.answer_slots import AnswerSlots
from dashagent.canonical_data_renderer import render_canonical_data_answer


def _slots(query: str, **kwargs) -> AnswerSlots:
    defaults = {"query": query, "answer_family": "journey_campaign"}
    defaults.update(kwargs)
    return AnswerSlots(**defaults)


def _decision(intent: str) -> AnswerIntentDecision:
    mode = "CANONICAL_CAVEAT" if intent == "ERROR_CAVEAT" else "CANONICAL_DATA"
    return AnswerIntentDecision(answer_intent=intent, answer_mode=mode, confidence="HIGH", reason_codes=["unit"])


def test_count_local_snapshot_renders_exact_count_and_scope() -> None:
    slots = _slots("How many schema records are in the local snapshot?", counts=[2], sql_row_count=1)

    rendered = render_canonical_data_answer("How many schema records are in the local snapshot?", _decision("COUNT"), slots)

    assert rendered.answer == "There are 2 schema records in the local snapshot."
    assert rendered.rendered_roles == ["COUNT", "SCOPE"]


def test_date_renders_entity_and_iso_date() -> None:
    slots = _slots("When was Birthday Message published?", entity_names=["Birthday Message"], timestamps=["2026-03-31T06:07:32Z"])

    rendered = render_canonical_data_answer(slots.query, _decision("DATE"), slots)

    assert rendered.answer == "Birthday Message was published on 2026-03-31."
    assert rendered.rendered_roles == ["ENTITY", "DATE"]


def test_status_renders_entity_and_status() -> None:
    slots = _slots("Show Birthday Message status.", entity_names=["Birthday Message"], statuses=["draft"])

    rendered = render_canonical_data_answer(slots.query, _decision("STATUS"), slots)

    assert rendered.answer == "Birthday Message is draft."
    assert rendered.rendered_roles == ["ENTITY", "STATUS"]


def test_list_renders_concise_semicolon_list() -> None:
    slots = _slots("Give me inactive journeys.", entity_names=["Birthday Message", "Gold Tier Welcome Email"])

    rendered = render_canonical_data_answer(slots.query, _decision("LIST"), slots)

    assert rendered.answer == "Journeys: Birthday Message; Gold Tier Welcome Email."
    assert rendered.rendered_roles == ["LIST"]


def test_api_error_does_not_become_no_data() -> None:
    slots = _slots("Show current schemas.", api_error=True, answer_slot_source="api_error")

    rendered = render_canonical_data_answer(slots.query, _decision("ERROR_CAVEAT"), slots, evidence_quality={"api": ["API_ERROR"]})

    assert rendered.answer == "API unavailable/error; cannot verify live state."
    assert "no matching" not in rendered.answer.lower()


def test_live_empty_is_scoped() -> None:
    slots = _slots("Show current schemas.", api_evidence_state="live_empty")

    rendered = render_canonical_data_answer(slots.query, _decision("ERROR_CAVEAT"), slots, evidence_quality={"api": ["API_LIVE_EMPTY"]})

    assert rendered.answer == "No matching records were returned for this query/scope."
    assert "globally" not in rendered.answer.lower()


def test_missing_fields_are_not_invented() -> None:
    slots = _slots("Show Birthday Message status.", entity_names=["Birthday Message"])

    rendered = render_canonical_data_answer(slots.query, _decision("STATUS"), slots)

    assert "published" not in rendered.answer.lower()
    assert "inactive" not in rendered.answer.lower()
    assert "STATUS" in rendered.missing_roles
