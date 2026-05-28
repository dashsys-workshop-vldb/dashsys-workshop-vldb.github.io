from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.concise_rewrite_card import build_concise_rewrite_card
from dashagent.concise_rewrite_eligibility import decide_concise_rewrite_eligibility
from dashagent.config import DEFAULT_CONFIG, SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE
from dashagent.eval_harness import config_for_applied_trial_strategy
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY


def _slots(query: str, **overrides) -> AnswerSlots:
    slots = AnswerSlots(query=query, answer_family=overrides.pop("answer_family", "unit"))
    for key, value in overrides.items():
        setattr(slots, key, value)
    return slots


def test_count_with_exact_runtime_fact_is_rewrite_eligible() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], evidence_numbers={"74"})

    decision = decide_concise_rewrite_eligibility(
        prompt=slots.query,
        legacy_answer="The local snapshot contains 74 schema records.",
        slots=slots,
    )

    assert decision.eligible is True
    assert decision.answer_type == "COUNT"
    assert decision.risk == "LOW"
    assert "ELIGIBLE_COUNT_EXACT_FACTS" in decision.reason_codes


def test_legacy_already_concise_is_not_eligible() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], evidence_numbers={"74"})

    decision = decide_concise_rewrite_eligibility(
        prompt=slots.query,
        legacy_answer="You have 74 schemas.",
        slots=slots,
    )

    assert decision.eligible is False
    assert "LEGACY_ALREADY_CONCISE" in decision.reason_codes


def test_complex_multi_field_list_not_eligible() -> None:
    slots = _slots(
        "List schemas with IDs, statuses, and published dates.",
        entity_names=["Profile Schema"],
        entity_ids=["schema-1"],
        statuses=["active"],
        timestamps=["2026-03-31"],
    )

    decision = decide_concise_rewrite_eligibility(
        prompt=slots.query,
        legacy_answer="Profile Schema (schema-1), status active, published 2026-03-31.",
        slots=slots,
    )

    assert decision.eligible is False
    assert "COMPLEX_MULTI_FIELD_LIST" in decision.reason_codes


def test_api_error_sensitive_caveat_not_eligible() -> None:
    slots = _slots(
        "List schemas.",
        entity_names=["Profile Schema"],
        api_error=True,
        api_errors=["timeout"],
    )

    decision = decide_concise_rewrite_eligibility(
        prompt=slots.query,
        legacy_answer="API unavailable/error; cannot verify live state.",
        slots=slots,
    )

    assert decision.eligible is False
    assert decision.risk == "HIGH"
    assert "CAVEAT_SENSITIVE" in decision.reason_codes


def test_rewrite_card_excludes_evaluator_only_fields() -> None:
    slots = _slots(
        "When was Birthday Message published?",
        entity_names=["Birthday Message"],
        timestamps=["2026-03-31"],
        evidence_strings={"birthday message", "2026-03-31"},
    )
    decision = decide_concise_rewrite_eligibility(
        prompt=slots.query,
        legacy_answer="Birthday Message has published_time 2026-03-31.",
        slots=slots,
    )

    card = build_concise_rewrite_card(
        prompt=slots.query,
        legacy_answer="Birthday Message has published_time 2026-03-31.",
        slots=slots,
        eligibility=decision,
    )
    payload = card.to_dict()
    serialized = str(payload).lower()

    for forbidden in ("gold", "category", "tags", "oracle", "expected_trace", "query_id", "prompt_id"):
        assert forbidden not in serialized


def test_strategy_is_explicit_only_and_default_remains_sql_first(tiny_project) -> None:
    from dashagent.planner import ALL_STRATEGIES, STRATEGIES, execution_base_strategy

    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE in ALL_STRATEGIES
    assert SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE not in STRATEGIES
    assert execution_base_strategy(SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE) == "SQL_FIRST_API_VERIFY"

    cfg = config_for_applied_trial_strategy(tiny_project, SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE)
    assert DEFAULT_CONFIG.enable_concise_llm_rewrite is False
    assert cfg.enable_concise_llm_rewrite is True
    assert cfg.enable_hybrid_answer_composer is False
    assert cfg.enable_staged_evidence_policy is False
    assert cfg.enable_safe_api_probe is False
    assert cfg.real_behavior_trial_mode == SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE
