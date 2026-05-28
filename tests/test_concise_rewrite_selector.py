from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.concise_llm_answer_rewriter import ConciseRewriteResult
from dashagent.concise_rewrite_card import build_concise_rewrite_card
from dashagent.concise_rewrite_eligibility import decide_concise_rewrite_eligibility
from dashagent.concise_rewrite_selector import select_concise_rewrite


def _slots(query: str, **overrides) -> AnswerSlots:
    slots = AnswerSlots(query=query, answer_family=overrides.pop("answer_family", "unit"))
    for key, value in overrides.items():
        setattr(slots, key, value)
    return slots


def _card(prompt: str, legacy: str, slots: AnswerSlots):
    eligibility = decide_concise_rewrite_eligibility(prompt=prompt, legacy_answer=legacy, slots=slots)
    return build_concise_rewrite_card(prompt=prompt, legacy_answer=legacy, slots=slots, eligibility=eligibility)


def _result(answer: str, category: str = "ok") -> ConciseRewriteResult:
    return ConciseRewriteResult(
        rewritten_answer=answer,
        category=category,
        attempted=True,
        backend_available=category != "backend_unavailable",
        raw_response_present=bool(answer),
        extracted_content_length=len(answer),
    )


def test_count_rewrite_selected_when_shorter_and_equal_facts() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], evidence_numbers={"74"})
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("You have 74 schemas."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "CONCISE_LLM_REWRITE"
    assert selected.selected_answer == "You have 74 schemas."
    assert "SELECT_REWRITE_SHORTER_EQUAL_FACTS" in selected.selection_codes


def test_date_rewrite_preserves_entity_and_exact_iso_date() -> None:
    slots = _slots("When was Birthday Message published?", entity_names=["Birthday Message"], timestamps=["2026-03-31"])
    legacy = "Birthday Message has published_time 2026-03-31."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("Birthday Message was published on 2026-03-31."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "CONCISE_LLM_REWRITE"


def test_status_rewrite_preserves_entity_and_status() -> None:
    slots = _slots("What is Journey A status?", entity_names=["Journey A"], statuses=["inactive"])
    legacy = "Journey A has status inactive."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("Journey A is inactive."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "CONCISE_LLM_REWRITE"


def test_list_rewrite_preserves_all_items() -> None:
    slots = _slots(
        "Give me inactive journeys",
        entity_names=["Birthday Message", "Gold Tier Welcome Email"],
        statuses=["inactive"],
    )
    legacy = "Based on the SQL evidence, the matching item(s) are: Birthday Message, Gold Tier Welcome Email."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("Inactive journeys: Birthday Message; Gold Tier Welcome Email."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "CONCISE_LLM_REWRITE"


def test_unsupported_number_rejected() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("You have 75 schemas."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "KEEP_LEGACY_MISSING_EXACT_FACT" in selected.selection_codes


def test_local_to_live_scope_change_rejected() -> None:
    slots = _slots("How many schema records are in the local snapshot?", counts=[74])
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("Adobe Experience Platform has 74 schemas."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "KEEP_LEGACY_SCOPE_RISK" in selected.selection_codes


def test_extra_api_caveat_rejected() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("You have 74 schemas. API unavailable/error; cannot verify live state."),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "KEEP_LEGACY_EXTRA_CAVEAT" in selected.selection_codes


def test_empty_rewrite_rejected() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("", category="empty_rewrite"),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "KEEP_LEGACY_EMPTY_REWRITE" in selected.selection_codes


def test_backend_unavailable_keeps_legacy() -> None:
    slots = _slots("How many schemas do I have?", counts=[74])
    legacy = "The local snapshot contains 74 schema records."
    card = _card(slots.query, legacy, slots)

    selected = select_concise_rewrite(
        prompt=slots.query,
        legacy_answer=legacy,
        rewrite_result=_result("", category="backend_unavailable"),
        card=card,
        slots=slots,
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "KEEP_LEGACY_BACKEND_UNAVAILABLE" in selected.selection_codes
