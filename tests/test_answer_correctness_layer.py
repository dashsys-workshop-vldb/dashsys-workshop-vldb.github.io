from __future__ import annotations

import json

from dashagent.answer_claims import extract_claims
from dashagent.answer_intent import AnswerIntent, classify_answer_intent
from dashagent.answer_reranker import select_best_answer
from dashagent.answer_slots import extract_answer_slots
from dashagent.answer_synthesizer import synthesize_answer, synthesize_answer_with_diagnostics
from dashagent.answer_verifier import verify_answer
from dashagent.executor import AgentExecutor


def test_slot_extraction_from_sql_dry_run_and_live_api():
    query = "List segment audiences connected to destination named 'SMS Opt-In'"
    tool_results = [
        {
            "type": "sql",
            "payload": {
                "ok": True,
                "rows": [
                    {
                        "segment_id": "s1",
                        "segment_name": "Audience A",
                        "total_profiles": 12,
                        "updated_time": "2026-03-31T00:00:00Z",
                    }
                ],
                "row_count": 1,
            },
        },
        {
            "type": "api",
            "step": {"family": "audience_by_destination_id"},
            "payload": {
                "ok": True,
                "result_preview": {"items": [{"id": "aud1", "name": "Audience A", "status": "active"}], "total": 1},
            },
        },
        {"type": "api", "step": {"family": "destination_flows"}, "payload": {"ok": False, "dry_run": True}},
    ]
    slots = extract_answer_slots(query, tool_results)
    assert slots.sql_row_count == 1
    assert slots.api_item_count == 1
    assert slots.dry_run is True
    assert "Audience A" in slots.entity_names
    assert "s1" in slots.entity_ids
    assert "active" in slots.statuses
    assert "2026-03-31T00:00:00Z" in slots.timestamps


def test_intent_classification_count_list_when_status_no_result():
    assert classify_answer_intent("How many tags exist?", None) == AnswerIntent.COUNT
    assert classify_answer_intent("List all tags", None) == AnswerIntent.LIST
    assert classify_answer_intent("When was the journey published?", None) == AnswerIntent.WHEN
    assert classify_answer_intent("Show jobs with status QUEUED", None) == AnswerIntent.STATUS
    slots = extract_answer_slots("Show missing records", [{"type": "sql", "payload": {"ok": True, "rows": [], "row_count": 0}}])
    assert classify_answer_intent("Show missing records", slots) == AnswerIntent.NO_RESULT


def test_claim_extraction_and_verifier_rejects_unsupported_facts():
    slots = extract_answer_slots(
        "How many tags exist?",
        [{"type": "api", "step": {"family": "tag_count"}, "payload": {"ok": False, "dry_run": True}}],
    )
    unsupported = "The API confirmed 2 tags."
    claims = extract_claims(unsupported)
    assert any(claim.claim_type == "number" and claim.value == "2" for claim in claims)
    result = verify_answer(unsupported, slots)
    assert result.ok is False
    assert "api_confirmation_without_live_api" in result.errors

    safe = "The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable."
    assert verify_answer(safe, slots).ok is True


def test_reranker_prefers_verifier_passing_intent_answer():
    query = "How many tags exist in this sandbox?"
    tool_results = [{"type": "api", "step": {"family": "tag_count"}, "payload": {"ok": False, "dry_run": True}}]
    selection = select_best_answer(query, tool_results, "The API confirmed 2 tags.")
    assert selection.answer.startswith("The tag count")
    assert selection.diagnostics["verifier_passed"] is True
    assert selection.diagnostics["selected_candidate_type"] != "base"


def test_weak_family_answers_are_intent_matched_and_dry_run_safe():
    batch = synthesize_answer(
        "How many batches have status 'success'?",
        [{"type": "api", "step": {"family": "successful_batch_count"}, "payload": {"ok": False, "dry_run": True}}],
    )
    assert batch.startswith("The batch count")
    assert "Live API verification was not executed" in batch

    tags = synthesize_answer(
        "List all tags in this sandbox.",
        [{"type": "api", "step": {"family": "tag_list"}, "payload": {"ok": False, "dry_run": True}}],
    )
    assert "tag list requires live API evidence" in tags

    segment_jobs = synthesize_answer(
        "Show all segment jobs with status 'QUEUED'.",
        [{"type": "api", "step": {"family": "segment_jobs"}, "payload": {"ok": False, "dry_run": True}}],
    )
    assert "segment evaluation job" in segment_jobs.lower()
    assert "Live API verification was not executed" in segment_jobs

    merge = synthesize_answer(
        "How many merge policies are configured in this sandbox?",
        [{"type": "api", "step": {"family": "merge_policies"}, "payload": {"ok": False, "dry_run": True}}],
    )
    assert merge.startswith("The merge policy count")


def test_live_like_family_answers_use_payload_evidence_only():
    tag_answer = synthesize_answer(
        "Show me the details of the tag named 'cool'.",
        [
            {
                "type": "api",
                "step": {"family": "tag_details_by_id"},
                "payload": {
                    "ok": True,
                    "result_preview": {"id": "tag1", "name": "cool", "tagCategoryId": "cat1"},
                },
            }
        ],
    )
    assert "cool" in tag_answer
    assert "tag1" in tag_answer

    batch_answer = synthesize_answer(
        "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?",
        [
            {
                "type": "api",
                "step": {"family": "batch_export_files"},
                "payload": {
                    "ok": True,
                    "result_preview": {"files": [{"id": "file1", "fileName": "part-000.json", "status": "invalid"}]},
                },
            }
        ],
    )
    assert "part-000.json" in batch_answer


def test_synthesizer_returns_compact_diagnostics():
    result = synthesize_answer_with_diagnostics(
        "How many tags exist?",
        [{"type": "api", "step": {"family": "tag_count"}, "payload": {"ok": False, "dry_run": True}}],
    )
    assert result.diagnostics["answer_family"] == "tags"
    assert result.diagnostics["answer_intent"] == "COUNT"
    assert set(result.diagnostics) == {
        "answer_family",
        "answer_intent",
        "slots_present",
        "verifier_passed",
        "unsupported_claims_count",
        "completeness_missing_fields",
        "rewrite_applied",
        "selected_candidate_type",
    }


def test_executor_trajectory_includes_answer_diagnostics_and_budget(tiny_project):
    executor = AgentExecutor(tiny_project)
    result = executor.run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="answer_diag_budget")
    kinds = [step["kind"] for step in result["trajectory"]["steps"]]
    assert "answer_diagnostics" in kinds
    assert result["trajectory"]["tool_call_count"] == 1
    text = json.dumps(result["trajectory"])
    assert "answer_family" in text
