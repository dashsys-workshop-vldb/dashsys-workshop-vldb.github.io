from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.run_score_focused_core_improvement_trials import (
    VARIANTS,
    apply_score_focused_variant,
    run_score_focused_core_improvement_trials,
)
from scripts.run_score_path_contribution_audit import run_score_path_contribution_audit
from scripts.generate_consolidated_reports import generate_consolidated_reports


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_md(path: Path, text: str = "# report\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_score_path_reports(outputs: Path) -> None:
    reports = outputs / "reports"
    visualizations = outputs / "visualizations"
    _write_md(visualizations / "full_project_dataflow.svg", "SQL_FIRST_API_VERIFY EvidenceBus live_success guard")
    _write_json(
        visualizations / "full_project_dataflow.json",
        {
            "packaged_strategy": "SQL_FIRST_API_VERIFY",
            "strict_score": 0.6553,
            "hidden_style": "48/48",
            "final_submission_ready": True,
            "live_success_count": 0,
            "live_guard_status": "blocked",
        },
    )
    _write_json(
        reports / "workflow_decision_audit.json",
        {
            "bottleneck_distribution": {
                "answer_uses_dry_run_poorly": 5,
                "api_only_needs_live_credentials": 20,
            },
            "rows": [],
        },
    )
    _write_json(
        reports / "accuracy_and_bottleneck_summary.json",
        {"answer_quality_bottleneck": True, "dry_run_api_limitation": True},
    )
    _write_json(
        reports / "evidence_usage_audit.json",
        {
            "category_distribution": {"answer_missing_count": 3, "zero_row_answer_unclear": 2},
            "summary": {"dry_run_caveat_rows": 5},
            "rows": [],
        },
    )
    _write_json(
        reports / "sql_evidence_usage_audit.json",
        {
            "summary": {
                "issue_distribution": {"answer_missed_count": 4, "zero_row_answer_unclear": 4},
                "zero_row_unclear_rows": 4,
            },
            "rows": [],
        },
    )
    _write_json(
        reports / "evidence_aware_answer_rewrite_trial.json",
        {"summary": {"best_strict_score_delta": -0.0327}, "official_score_claim": False},
    )
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "rows": [],
            "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6553}}},
        },
    )


def _seed_trial_eval(outputs: Path, *, final_answer: str | None = None) -> Path:
    query_id = "tiny_001"
    output_dir = outputs / "eval" / query_id / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    answer = final_answer or (
        "Live API verification was not executed because Adobe credentials are unavailable. "
        "SQL found matching local records."
    )
    trajectory = {
        "query_id": query_id,
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL_THEN_API",
        "domain_type": "JOURNEY_CAMPAIGN",
        "final_answer": answer,
        "tool_call_count": 2,
        "sql_call_count": 1,
        "api_call_count": 1,
        "runtime": 0.01,
        "estimated_tokens": 100,
        "steps": [
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                "result": {
                    "ok": True,
                    "row_count": 1,
                    "rows": {"items": [{"count": 2}], "total_items": 1, "truncated_items": False},
                },
            },
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/ajo/journey",
                "params": {},
                "result": {"ok": False, "dry_run": True, "endpoint": "/ajo/journey"},
            },
        ],
        "checkpoints": [],
    }
    _write_json(output_dir / "trajectory.json", trajectory)
    _write_json(output_dir / "metadata.json", {"query_id": query_id})
    (output_dir / "filled_system_prompt.txt").write_text("tiny prompt\n", encoding="utf-8")
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "strict": True,
            "rows": [
                {
                    "query_id": query_id,
                    "query": "How many campaigns are there?",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "output_dir": str(output_dir),
                    "final_score": 0.5,
                    "answer_score": 0.1,
                    "sql_score": 1.0,
                    "api_score": 1.0,
                    "tool_call_count": 2,
                    "estimated_tokens": 100,
                    "runtime": 0.01,
                }
            ],
            "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.5}}},
        },
    )
    return output_dir / "trajectory.json"


def test_score_path_audit_classifies_score_relevant_components(tiny_project):
    _seed_score_path_reports(tiny_project.outputs_dir)

    payload = run_score_path_contribution_audit(tiny_project)

    reports = tiny_project.outputs_dir / "reports"
    assert (reports / "score_path_contribution_audit.json").exists()
    assert (reports / "score_path_contribution_audit.md").exists()
    assert payload["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert payload["live_success_count"] == 0
    assert payload["classifications"]["direct_score_path"]["answer_synthesis"]["score_relevance"] == "can_improve_now"
    assert payload["classifications"]["external_blocker"]["Adobe sandbox permission"]["score_relevance"] == "blocked_by_adobe_access"
    assert payload["conclusions"]["primary_score_focus"] == [
        "answer synthesis",
        "SQL evidence usage",
        "dry-run wording",
    ]
    assert payload["conclusions"]["do_not_touch_for_score_now"]


def test_score_focused_variant_keeps_sql_answer_before_dry_run_caveat(tiny_project):
    trajectory_path = _seed_trial_eval(tiny_project.outputs_dir)
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))

    candidate = apply_score_focused_variant(trajectory, "dry_run_caveat_after_sql_answer")

    assert candidate["final_answer"].startswith("Based on the SQL evidence")
    assert "2" in candidate["final_answer"]
    assert "Live API verification" in candidate["final_answer"]
    assert candidate["steps"] == trajectory["steps"]


def test_score_focused_trials_are_isolated_and_trial_only(tiny_project):
    _seed_trial_eval(tiny_project.outputs_dir)
    before = json.loads((tiny_project.outputs_dir / "eval_results_strict.json").read_text(encoding="utf-8"))

    payload = run_score_focused_core_improvement_trials(tiny_project)

    after = json.loads((tiny_project.outputs_dir / "eval_results_strict.json").read_text(encoding="utf-8"))
    assert after == before
    assert payload["official_score_claim"] is False
    assert payload["writes_eval_outputs"] is False
    assert payload["writes_final_submission"] is False
    assert set(payload["variants"]) == set(VARIANTS)
    assert payload["fix_decision"]["runtime_change_applied"] is False
    assert payload["fix_decision"]["promotion_safe"] is False
    assert (tiny_project.outputs_dir / "reports" / "score_focused_core_fix_decision.json").exists()
    for variant in VARIANTS:
        assert (tiny_project.outputs_dir / "score_focused_core_improvement_trials" / variant / "tiny_001" / "trajectory.json").exists()


def test_zero_row_variant_uses_local_evidence_specific_wording(tiny_project):
    trajectory_path = _seed_trial_eval(tiny_project.outputs_dir)
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    zero_row = copy.deepcopy(trajectory)
    zero_row["steps"][0]["result"]["row_count"] = 0
    zero_row["steps"][0]["result"]["rows"] = {"items": [], "total_items": 0, "truncated_items": False}

    candidate = apply_score_focused_variant(zero_row, "zero_row_local_evidence_clarity")

    assert "No matching local records were found in the available local evidence." in candidate["final_answer"]
    assert "there is no data" not in candidate["final_answer"].lower()
    assert "Live API verification" in candidate["final_answer"]


def test_score_path_reports_are_linked_from_consolidated_index(tiny_project):
    _seed_score_path_reports(tiny_project.outputs_dir)
    _seed_trial_eval(tiny_project.outputs_dir)
    run_score_path_contribution_audit(tiny_project)
    run_score_focused_core_improvement_trials(tiny_project)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    assert "python3 scripts/run_score_path_contribution_audit.py" in index["post_change_validation"]["required_commands"]
    assert "python3 scripts/run_score_focused_core_improvement_trials.py" in index["post_change_validation"]["required_commands"]
    assert "outputs/reports/score_path_contribution_audit.md/json" in index["post_change_validation"]["report_regeneration_targets"]
    assert "outputs/reports/score_focused_core_improvement_trials.md/json" in index["post_change_validation"]["report_regeneration_targets"]
    score_reports = index["score_focused_core_path"]
    assert score_reports["contribution_audit_path"] == "outputs/reports/score_path_contribution_audit.md"
    assert score_reports["fix_decision_path"] == "outputs/reports/score_focused_core_fix_decision.md"
    assert score_reports["runtime_change_applied"] is False
    assert score_reports["recommendation"] in {
        "keep_trial_only",
        "multiple_candidates_require_separate_approval",
        "promote_single_winner_after_validation",
    }
