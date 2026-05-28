from __future__ import annotations

from dataclasses import replace

from dashagent.answer_slots import AnswerSlots
from dashagent.config import DEFAULT_CONFIG
from dashagent.evidence_allowed_fact_index import build_allowed_fact_index
from dashagent.evidence_bus import EvidenceBus
from dashagent.evidence_grounded_final_answer_verifier import (
    verify_evidence_grounded_final_answer,
    verify_or_rewrite_final_answer,
)
from dashagent.final_answer_claim_extractor import extract_final_answer_claims
from dashagent.final_answer_claim_matcher import match_final_answer_claims
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY


class FakeJudgeClient:
    def complete(self, messages):
        return "SUPPORTED"


class UnavailableJudgeClient:
    def complete(self, messages):
        raise RuntimeError("backend unavailable")


class RewriteClient:
    def __init__(self, rewritten: str) -> None:
        self.rewritten = rewritten

    def complete(self, messages):
        return self.rewritten


def _slots() -> AnswerSlots:
    return AnswerSlots(
        query="Show Birthday Message status",
        answer_family="status",
        entity_names=["Birthday Message"],
        entity_ids=["cmp-123"],
        counts=[2],
        statuses=["published"],
        timestamps=["2026-05-01T12:00:00Z"],
        first_rows=[
            {
                "id": "cmp-123",
                "name": "Birthday Message",
                "status": "published",
                "createdTime": "2026-05-01T12:00:00Z",
            }
        ],
        evidence_strings={"birthday message", "cmp-123", "published", "2026-05-01t12:00:00z"},
        evidence_numbers={"2"},
    )


def _live_empty_slots() -> AnswerSlots:
    return AnswerSlots(
        query="List matching schemas",
        answer_family="list",
        api_evidence_state="live_empty",
        answer_slot_source="live_api",
        live_api_evidence_available=False,
    )


def _api_error_slots() -> AnswerSlots:
    return AnswerSlots(
        query="List matching schemas",
        answer_family="list",
        api_error=True,
        api_errors=["timeout"],
        answer_slot_source="api_error",
    )


def test_allows_different_wording_for_supported_status() -> None:
    result = verify_evidence_grounded_final_answer("Birthday Message is published.", slots=_slots())

    assert result.ok is True
    assert result.unsupported_claims == []


def test_allows_bullet_format_for_same_supported_facts() -> None:
    answer = "- Name: Birthday Message\n- Status: published\n- ID: cmp-123"

    result = verify_evidence_grounded_final_answer(answer, slots=_slots())

    assert result.ok is True


def test_allows_harmless_discourse_phrase() -> None:
    result = verify_evidence_grounded_final_answer(
        "Based on the available evidence, Birthday Message is published.",
        slots=_slots(),
    )

    assert result.ok is True


def test_blocks_invented_count() -> None:
    result = verify_evidence_grounded_final_answer("There are 3 matching campaigns.", slots=_slots())

    assert result.ok is False
    assert any(claim["type"] == "COUNT" for claim in result.unsupported_claims)


def test_blocks_invented_id() -> None:
    result = verify_evidence_grounded_final_answer("The ID is cmp-999.", slots=_slots())

    assert result.ok is False
    assert any(claim["type"] == "ID" for claim in result.unsupported_claims)


def test_blocks_invented_timestamp() -> None:
    result = verify_evidence_grounded_final_answer("It was created on 2026-06-02.", slots=_slots())

    assert result.ok is False
    assert any(claim["type"] == "DATE" for claim in result.unsupported_claims)


def test_blocks_invented_status() -> None:
    result = verify_evidence_grounded_final_answer("Birthday Message is inactive.", slots=_slots())

    assert result.ok is False
    assert any(claim["type"] == "STATUS" for claim in result.unsupported_claims)


def test_blocks_unsupported_relationship() -> None:
    result = verify_evidence_grounded_final_answer("Birthday Message uses dataset ProfileStore.", slots=_slots())

    assert result.ok is False
    assert any(claim["type"] == "RELATIONSHIP" for claim in result.unsupported_claims)


def test_blocks_live_empty_as_global_absence() -> None:
    result = verify_evidence_grounded_final_answer("There are no schemas anywhere.", slots=_live_empty_slots())

    assert result.ok is False
    assert result.over_specified_claims


def test_blocks_live_empty_scoped_phrase_with_global_overreach() -> None:
    result = verify_evidence_grounded_final_answer(
        "No matching records were returned for this query globally.",
        slots=_live_empty_slots(),
        caveats=["API_LIVE_EMPTY"],
    )

    assert result.ok is False
    assert result.over_specified_claims


def test_allows_live_empty_as_scoped_empty() -> None:
    result = verify_evidence_grounded_final_answer(
        "No matching records were returned for this query scope.",
        slots=_live_empty_slots(),
        caveats=["API_LIVE_EMPTY"],
    )

    assert result.ok is True


def test_blocks_api_error_as_no_data() -> None:
    result = verify_evidence_grounded_final_answer("There are no schemas.", slots=_api_error_slots())

    assert result.ok is False
    assert result.unsupported_claims or result.needs_caveat_claims


def test_allows_api_error_as_unavailable() -> None:
    result = verify_evidence_grounded_final_answer("API unavailable; live state could not be verified.", slots=_api_error_slots())

    assert result.ok is True


def test_missing_role_not_invented() -> None:
    slots = replace(_slots(), timestamps=[], evidence_strings={"birthday message", "cmp-123", "published"})

    result = verify_evidence_grounded_final_answer("Updated time is 2026-05-03.", slots=slots, missing_roles=["UPDATED_TIME"])

    assert result.ok is False
    assert result.unsupported_claims


def test_ambiguous_claim_can_be_judged_by_llm_judge() -> None:
    slots = replace(_slots(), entity_names=["Birthday Message"], evidence_strings={"birthday message"})

    result = verify_evidence_grounded_final_answer(
        "The matching campaign is Birthday Message.",
        slots=slots,
        llm_judge_enabled=True,
        llm_client=FakeJudgeClient(),
    )

    assert result.ok is True
    assert any(claim["type"] == "EXISTENCE" for claim in result.supported_claims)


def test_backend_unavailable_falls_back_safely_for_ambiguous_claim() -> None:
    result = verify_evidence_grounded_final_answer(
        "The matching campaign looks ready.",
        slots=_slots(),
        llm_judge_enabled=True,
        llm_client=UnavailableJudgeClient(),
    )

    assert result.ok is False
    assert result.needs_caveat_claims


def test_rewrite_feedback_removes_unsupported_claim() -> None:
    result = verify_or_rewrite_final_answer(
        "There are 3 matching campaigns.",
        deterministic_answer="Count: 2.",
        slots=_slots(),
        rewrite_client=RewriteClient("There are 2 matching campaigns."),
    )

    assert result.first_pass_ok is False
    assert result.rewrite_attempted is True
    assert result.rewrite_success is True
    assert result.fallback_used is False
    assert result.final_answer == "There are 2 matching campaigns."
    assert result.feedback["task"] == "REWRITE_FINAL_ANSWER"
    assert "allowed_fact_index" not in result.feedback


def test_deterministic_fallback_used_after_failed_rewrite() -> None:
    result = verify_or_rewrite_final_answer(
        "There are 3 matching campaigns.",
        deterministic_answer="Count: 2.",
        slots=_slots(),
        rewrite_client=RewriteClient("There are 4 matching campaigns."),
    )

    assert result.rewrite_attempted is True
    assert result.rewrite_success is False
    assert result.fallback_used is True
    assert result.final_answer == "Count: 2."


def test_live_empty_global_no_data_feedback_is_minimal() -> None:
    result = verify_or_rewrite_final_answer(
        "There are no schemas in AEP.",
        deterministic_answer="No matching records were returned for this query scope.",
        slots=_live_empty_slots(),
        caveats=["API_LIVE_EMPTY"],
        rewrite_client=RewriteClient("No matching schema records were returned for this API query."),
    )

    assert result.first_pass_ok is False
    assert result.feedback["task"] == "REWRITE_FINAL_ANSWER"
    assert result.feedback["blocked_claims"][0]["issue"] == "LIVE_EMPTY_AS_GLOBAL_ABSENCE"
    assert result.feedback["allowed_facts"]
    assert "GLOBAL_NO_DATA" in result.feedback["forbidden_claim_types"]
    assert "allowed_fact_index" not in result.feedback


def test_api_error_no_data_feedback_is_minimal() -> None:
    result = verify_or_rewrite_final_answer(
        "There are no schemas.",
        deterministic_answer="API unavailable; live state could not be verified.",
        slots=_api_error_slots(),
        rewrite_client=RewriteClient("API unavailable; live state could not be verified."),
    )

    assert result.first_pass_ok is False
    assert result.feedback["task"] == "REWRITE_FINAL_ANSWER"
    assert any(item["role"] == "CAVEAT" and item["value"] == "API_ERROR" for item in result.feedback["allowed_facts"])
    assert "NO_DATA_FROM_API_ERROR" in result.feedback["forbidden_claim_types"]


def test_packaged_default_unchanged() -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert DEFAULT_CONFIG.enable_evidence_grounded_llm_answer_generator is False


def test_no_gold_category_tags_oracle_in_answer_fact_index() -> None:
    index = build_allowed_fact_index(
        slots=_slots(),
        answer_card={
            "gold_answer": "secret",
            "category": "api",
            "tags": ["private"],
            "oracle_sql": "select secret",
            "expected_trace": ["secret"],
        },
    )

    payload = index.to_dict()
    assert "gold_answer" not in str(payload)
    assert "oracle_sql" not in str(payload)
    assert "private" not in str(payload)


def test_claim_extractor_and_matcher_do_not_require_exact_wording() -> None:
    index = build_allowed_fact_index(slots=_slots())
    claims = extract_final_answer_claims("Available evidence says Birthday Message has status published.")
    matches = match_final_answer_claims(claims, index)

    assert all(match.status == "SUPPORTED" for match in matches)
