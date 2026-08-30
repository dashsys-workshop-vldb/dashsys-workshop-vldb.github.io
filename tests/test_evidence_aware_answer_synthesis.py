from __future__ import annotations

import json
from pathlib import Path

from dashagent.answer_faithfulness import evaluate_answer_faithfulness
from dashagent.answer_slots import extract_answer_slots
from dashagent.evidence_aware_answer_templates import compose_evidence_aware_answer
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.run_confidence_calibration_audit import run_confidence_calibration_audit
from scripts.run_evidence_aware_answer_rewrite_trial import (
    protected_deletion_preflight,
    run_evidence_aware_answer_rewrite_trial,
    selected_evidence_hash,
)
from scripts.run_evidence_usage_audit import run_evidence_usage_audit
from scripts.run_sql_evidence_usage_audit import run_sql_evidence_usage_audit
from scripts.run_token_efficiency_audit import run_token_efficiency_audit


def test_evidence_aware_templates_use_direct_facts():
    count = compose_evidence_aware_answer(
        "How many schemas do I have?",
        [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"schema_count": 2}]}}],
    )
    assert count.answer.startswith("You have 2")

    list_answer = compose_evidence_aware_answer(
        "List journeys",
        [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"name": "Birthday Message"}]}}],
    )
    assert "Birthday Message" in list_answer.answer

    status = compose_evidence_aware_answer(
        "What is the status of flow A?",
        [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"name": "flow A", "status": "active"}]}}],
    )
    assert status.answer.startswith("flow A is active")

    when = compose_evidence_aware_answer(
        "When was journey A updated?",
        [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"name": "journey A", "updatedAt": "2026-03-31T00:00:00Z"}]}}],
    )
    assert "2026-03-31" in when.answer


def test_evidence_state_templates_do_not_confuse_empty_dry_run_or_errors():
    live_empty = compose_evidence_aware_answer(
        "List journeys",
        [
            {
                "type": "api",
                "step": {"family": "journey_list"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "parsed_evidence": {
                        "ok": True,
                        "dry_run": False,
                        "evidence_state": "live_empty",
                        "items": [],
                        "live_evidence_available": True,
                    },
                },
            }
        ],
    )
    assert "no matching" in live_empty.answer.lower()
    assert "credentials" not in live_empty.answer.lower()

    dry_run = compose_evidence_aware_answer(
        "List journeys",
        [{"type": "api", "step": {"family": "journey_list"}, "payload": {"ok": False, "dry_run": True}}],
        api_required=True,
    )
    assert "verification was unavailable" in dry_run.answer.lower()
    assert "no matching" not in dry_run.answer.lower()
    assert dry_run.required_caveat_present is True

    api_error = compose_evidence_aware_answer(
        "List journeys",
        [{"type": "api", "step": {"family": "journey_list"}, "payload": {"ok": False, "dry_run": False, "error": "401"}}],
    )
    assert "api request failed" in api_error.answer.lower()
    assert "no matching" not in api_error.answer.lower()


def test_faithfulness_focuses_on_factual_drift_not_wording():
    slots = extract_answer_slots(
        "How many schemas do I have?",
        [{"type": "sql", "payload": {"ok": True, "row_count": 1, "rows": [{"schema_count": 2}]}}],
    )
    assert evaluate_answer_faithfulness("You have 2 schemas.", slots).unsupported_claims == []
    assert evaluate_answer_faithfulness("There are 2 schemas.", slots).unsupported_claims == []
    assert evaluate_answer_faithfulness("You have 3 schemas.", slots).unsupported_claims

    dry_slots = extract_answer_slots("List journeys", [{"type": "api", "payload": {"ok": False, "dry_run": True}}])
    assert not evaluate_answer_faithfulness("Live API verification was unavailable because credentials were not provided.", dry_slots).unsupported_claims
    assert evaluate_answer_faithfulness("Live API verification was unavailable because credentials were not provided.", slots).unsupported_claims


def test_selected_evidence_hash_excludes_final_answer_and_runtime_noise():
    trajectory = {
        "original_query": "How many schemas do I have?",
        "runtime": 1.0,
        "final_answer": "Baseline.",
        "tool_call_count": 1,
        "steps": [
            {"kind": "sql_call", "sql": "SELECT COUNT(*) AS count FROM dim_campaign", "result": {"ok": True, "row_count": 1, "rows": [{"count": 2}]}}
        ],
    }
    changed = json.loads(json.dumps(trajectory))
    changed["final_answer"] = "Candidate."
    changed["runtime"] = 99.0
    assert selected_evidence_hash(trajectory) == selected_evidence_hash(changed)


def test_answer_rewrite_trial_and_audits_are_isolated_and_parseable(tiny_project):
    _write_tiny_strict_artifact(tiny_project)

    assert protected_deletion_preflight(tiny_project)["blocked"] is False
    trial = run_evidence_aware_answer_rewrite_trial(tiny_project, limit=1, clean=True)
    assert trial["status"] == "complete"
    assert trial["writes_eval_outputs"] is False
    assert trial["writes_final_submission"] is False
    assert trial["summary"]["sql_api_score_delta"] == 0.0
    assert trial["final_decision"]["promotion_performed"] is False
    assert "evidence_aware_answer_rewrite_trial" in NON_SUBMISSION_OUTPUT_DIRS
    assert not (tiny_project.outputs_dir / "final_submission").exists()

    for runner, report_name in [
        (run_evidence_usage_audit, "evidence_usage_audit"),
        (run_sql_evidence_usage_audit, "sql_evidence_usage_audit"),
        (run_confidence_calibration_audit, "confidence_calibration_audit"),
        (run_token_efficiency_audit, "token_efficiency_audit"),
    ]:
        payload = runner(tiny_project)
        assert payload["status"] == "complete"
        path = tiny_project.outputs_dir / "reports" / f"{report_name}.json"
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8"))["report_type"] == report_name


def _write_tiny_strict_artifact(config) -> None:
    output_dir = config.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True)
    trajectory = {
        "query_id": "tiny_001",
        "strategy": "SQL_FIRST_API_VERIFY",
        "original_query": "How many campaigns are there?",
        "route_type": "SQL_ONLY",
        "domain_type": "JOURNEY_CAMPAIGN",
        "final_answer": "The database count is 2.",
        "tool_call_count": 1,
        "sql_call_count": 1,
        "api_call_count": 0,
        "runtime": 0.01,
        "estimated_tokens": 100,
        "steps": [
            {
                "kind": "route",
                "route_type": "SQL_ONLY",
                "domain_type": "JOURNEY_CAMPAIGN",
                "confidence": 0.8,
            },
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                "result": {"ok": True, "row_count": 1, "rows": [{"count": 2}]},
            },
        ],
        "checkpoints": [],
    }
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("test", encoding="utf-8")
    strict = {
        "rows": [
            {
                "query_id": "tiny_001",
                "strategy": "SQL_FIRST_API_VERIFY",
                "query": "How many campaigns are there?",
                "output_dir": str(output_dir),
                "final_score": 0.6,
                "answer_score": 0.5,
                "sql_score": 0.9,
                "api_score": None,
                "tool_call_count": 1,
                "estimated_tokens": 100,
                "runtime": 0.01,
            }
        ],
        "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6}}},
    }
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict, indent=2, sort_keys=True), encoding="utf-8")
