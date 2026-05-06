from __future__ import annotations

from dashagent.answer_shape import collect_shape_evidence, propose_answer_shape_candidate


def test_answer_shape_count_uses_recorded_sql_count():
    candidate = propose_answer_shape_candidate(
        "How many tags exist in this sandbox?",
        [{"type": "sql", "payload": {"ok": True, "rows": [{"count": 7}], "row_count": 1}}],
    )

    assert candidate.answer_shape == "count"
    assert candidate.supported is True
    assert "7" in candidate.text
    assert "sql_result" in candidate.source_evidence


def test_answer_shape_count_accepts_trajectory_preview_rows():
    candidate = propose_answer_shape_candidate(
        "How many schemas do I have?",
        [{"type": "sql", "payload": {"ok": True, "rows": {"items": [{"blueprint_count": 74}]}, "row_count": 1}}],
    )

    assert candidate.answer_shape == "count"
    assert candidate.supported is True
    assert "74" in candidate.text


def test_answer_shape_list_uses_sql_names():
    candidate = propose_answer_shape_candidate(
        "List all segment definitions.",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "rows": [{"name": "Audience A"}, {"name": "Audience B"}],
                    "row_count": 2,
                },
            }
        ],
    )

    assert candidate.answer_shape == "list"
    assert candidate.supported is True
    assert "Audience A" in candidate.text
    assert "Audience B" in candidate.text


def test_answer_shape_status_and_date_use_recorded_values():
    status = propose_answer_shape_candidate(
        "Show all segment jobs with status 'QUEUED'.",
        [{"type": "sql", "payload": {"ok": True, "rows": [{"id": "job1", "status": "QUEUED"}], "row_count": 1}}],
    )
    assert status.answer_shape == "status"
    assert "QUEUED" in status.text
    assert "job1" in status.text

    date = propose_answer_shape_candidate(
        "Which segment definitions were updated most recently?",
        [{"type": "sql", "payload": {"ok": True, "rows": [{"name": "Segment A", "updatedTime": "2026-04-01T01:02:03Z"}], "row_count": 1}}],
    )
    assert date.answer_shape == "date"
    assert "Segment A" in date.text
    assert "2026-04-01" in date.text


def test_answer_shape_detail_uses_query_visible_id_without_payload_fabrication():
    candidate = propose_answer_shape_candidate(
        "Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.",
        [
            {
                "type": "api",
                "step": {"family": "batch_detail", "params": {"batchId": "01KP69BPA5ZKFB7HCDYPE4GN6F"}},
                "payload": {
                    "ok": False,
                    "dry_run": True,
                    "result_preview": {"status": "success", "datasetId": "fabricated"},
                },
            }
        ],
    )

    assert candidate.answer_shape == "detail"
    assert "01KP69BPA5ZKFB7HCDYPE4GN6F" in candidate.text
    assert "success" not in candidate.text
    assert "fabricated" not in candidate.text
    assert "dry_run_api_no_payload" in candidate.source_evidence


def test_answer_shape_dry_run_unavailable_when_value_not_recorded():
    candidate = propose_answer_shape_candidate(
        "How many batches have status 'success'?",
        [
            {
                "type": "api",
                "step": {"family": "successful_batch_count"},
                "payload": {"ok": False, "dry_run": True, "result_preview": {"total": 99}},
            }
        ],
    )

    assert candidate.answer_shape == "count"
    assert candidate.supported is False
    assert candidate.unavailable_fields == ("count",)
    assert "unavailable in dry-run mode" in candidate.text
    assert "99" not in candidate.text


def test_answer_shape_does_not_echo_secret_like_params():
    evidence = collect_shape_evidence(
        "Show batch details.",
        [
            {
                "type": "api",
                "step": {
                    "family": "batch_detail",
                    "params": {"batchId": "batch-safe", "access_token": "secret-token", "client_secret": "also-secret"},
                },
                "payload": {"ok": False, "dry_run": True},
            }
        ],
    )

    assert evidence["safe_params"] == {"batchId": "batch-safe"}
    assert "secret-token" not in str(evidence)
    assert "also-secret" not in str(evidence)
