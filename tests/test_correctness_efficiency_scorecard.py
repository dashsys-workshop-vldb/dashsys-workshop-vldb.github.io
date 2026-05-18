from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_correctness_efficiency_scorecard import run_correctness_efficiency_scorecard


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_scorecard_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "rows": [
                {
                    "query_id": "example_001",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "correctness_score": 0.68,
                    "final_score": 0.65,
                    "sql_score": 0.93,
                    "api_score": 0.98,
                    "answer_score": 0.32,
                    "tool_call_count": 2,
                    "estimated_tokens": 900,
                    "runtime": 0.02,
                    "preprocessing_time": 0.01,
                    "planning_time": 0.002,
                    "execution_time": 0.003,
                    "answer_time": 0.001,
                },
                {
                    "query_id": "example_002",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "correctness_score": 0.7,
                    "final_score": 0.66,
                    "sql_score": 0.93,
                    "api_score": 0.98,
                    "answer_score": 0.34,
                    "tool_call_count": 1,
                    "estimated_tokens": 800,
                    "runtime": 0.01,
                    "preprocessing_time": 0.01,
                    "planning_time": 0.002,
                    "execution_time": 0.003,
                    "answer_time": 0.001,
                },
            ],
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_correctness_score": 0.69,
                        "avg_final_score": 0.655,
                        "avg_sql_score": 0.93,
                        "avg_api_score": 0.98,
                        "avg_answer_score": 0.33,
                        "avg_tool_call_count": 1.5,
                        "avg_estimated_tokens": 850,
                        "avg_runtime": 0.015,
                        "avg_preprocessing_time": 0.01,
                        "avg_planning_time": 0.002,
                        "avg_execution_time": 0.003,
                        "avg_answer_time": 0.001,
                    }
                }
            },
        },
    )
    _write_json(
        reports / "sdk_tool_calling_optimization_trials.json",
        {
            "report_type": "sdk_tool_calling_optimization_trials",
            "baseline_strict_score": 0.655,
            "generated_prompts_diagnostic_only": True,
            "writes_official_eval_artifacts": False,
            "writes_final_submission": False,
            "variants": [
                {
                    "variant_id": "compact_tool_schema",
                    "strict_score_delta": 0.0,
                    "answer_score_delta": 0.0,
                    "sql_score_delta": 0.0,
                    "api_score_delta": 0.0,
                    "token_input_estimate_delta": -60,
                    "token_output_estimate_delta": -20,
                    "tool_call_count_delta": 0,
                    "runtime_delta_seconds_estimate": -0.001,
                    "unsupported_claim_delta": 0,
                    "high_scoring_rows_hurt": 0,
                    "final_submission_format_changed": False,
                    "direct_http_hits": 0,
                    "hardcoded_query_id_trigger": False,
                    "hardcoded_prompt_id_trigger": False,
                    "hardcoded_exact_prompt_trigger": False,
                    "trial_mode": "artifact_replay",
                },
                {
                    "variant_id": "allowed_tools_by_prompt_type",
                    "strict_score_delta": 0.0,
                    "token_input_estimate_delta": 0,
                    "tool_call_count_delta": -4,
                    "runtime_delta_seconds_estimate": -0.04,
                    "unsupported_claim_delta": 0,
                    "high_scoring_rows_hurt": 0,
                    "final_submission_format_changed": False,
                    "direct_http_hits": 0,
                    "hardcoded_query_id_trigger": False,
                    "hardcoded_prompt_id_trigger": False,
                    "hardcoded_exact_prompt_trigger": False,
                    "trial_mode": "artifact_replay",
                },
                {
                    "variant_id": "regressing_speed_candidate",
                    "strict_score_delta": -0.02,
                    "token_input_estimate_delta": -100,
                    "tool_call_count_delta": -1,
                    "runtime_delta_seconds_estimate": -0.01,
                    "unsupported_claim_delta": 0,
                    "high_scoring_rows_hurt": 0,
                    "final_submission_format_changed": False,
                    "direct_http_hits": 0,
                    "hardcoded_query_id_trigger": False,
                    "hardcoded_prompt_id_trigger": False,
                    "hardcoded_exact_prompt_trigger": False,
                    "trial_mode": "artifact_replay",
                },
            ],
        },
    )
    _write_json(
        reports / "sdk_tool_calling_fix_decision.json",
        {
            "report_type": "sdk_tool_calling_fix_decision",
            "decision": "speed_only_shadow_candidates_no_promotion",
            "runtime_change_applied": False,
            "direct_http_hits": 0,
            "final_submission_format_changed": False,
        },
    )
    _write_json(
        reports / "score_focused_core_improvement_trials.json",
        {
            "report_type": "score_focused_core_improvement_trials",
            "variant_reports": [
                {
                    "variant": "answer_slot_trial",
                    "strict_score_delta": 0.0,
                    "token_delta_avg": 8,
                    "tool_delta_avg": 0,
                    "runtime_delta_avg": 0.0,
                    "unsupported_claim_delta": 0,
                    "high_score_regressions": 0,
                    "final_submission_would_change": True,
                }
            ],
        },
    )
    _write_json(
        reports / "system_summary.json",
        {
            "report_type": "system_summary",
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.655,
            "hidden_style": {"passed": 48, "total": 48, "label": "48/48"},
            "final_submission_ready": True,
        },
    )
    _write_json(
        reports / "accuracy_and_bottleneck_summary.json",
        {"report_type": "accuracy_and_bottleneck_summary", "starting_score": 0.655},
    )
    _write_json(
        reports / "sdk_usage_audit.json",
        {"report_type": "sdk_usage_audit", "summary": {"runtime_llm_direct_http_hits": 0}},
    )


def test_correctness_efficiency_scorecard_reports_scenarios_and_pareto(tiny_project):
    _seed_scorecard_inputs(tiny_project.outputs_dir)
    eval_hash = _sha256(tiny_project.outputs_dir / "eval_results_strict.json")

    payload = run_correctness_efficiency_scorecard(tiny_project)
    reports = tiny_project.outputs_dir / "reports"

    assert (reports / "correctness_efficiency_scorecard.json").exists()
    assert (reports / "correctness_efficiency_scorecard.md").exists()
    assert (reports / "correctness_efficiency_fix_decision.json").exists()
    assert (reports / "correctness_efficiency_fix_decision.md").exists()
    assert _sha256(tiny_project.outputs_dir / "eval_results_strict.json") == eval_hash
    assert not (tiny_project.outputs_dir / "final_submission").exists()

    scorecard = payload["scorecard"]
    assert scorecard["official_overall_score_claim"] is False
    assert scorecard["organizer_weights_known"] is False
    assert "tool_call_efficiency = baseline_tool_calls / max(variant_tool_calls, 1)" in scorecard["formulas"]
    assert {"correctness_dominant", "balanced", "efficiency_sensitive", "strict_no_regression_efficiency_rank", "hidden_safe_efficiency_rank"} <= set(scorecard["composite_scenarios"])

    compact = next(row for row in scorecard["variants"] if row["variant_id"] == "compact_tool_schema")
    assert compact["correctness_score"] == scorecard["baseline"]["correctness_score"]
    assert compact["efficiency"]["total_tokens_delta"] < 0
    assert compact["pareto_dominates_baseline"] is True
    assert compact["promotion_candidate_status"] in {"efficiency_candidate_needs_strict_validation", "safe_speed_patch_candidate"}
    assert "correctness_dominant" in compact["scenario_ranks"]

    regressing = next(row for row in scorecard["variants"] if row["variant_id"] == "regressing_speed_candidate")
    assert regressing["correctness_delta"] < 0
    assert regressing["promotion_candidate_status"] == "reject"
    assert regressing["pareto_dominates_baseline"] is False

    decision = payload["fix_decision"]
    assert decision["decision"] == "speed_only_patch_needs_validation"
    assert decision["runtime_change_applied"] is False
    assert decision["official_overall_score_claim"] is False
    assert decision["promotion_requirements"]["hidden_style_48_48_required"] is True
    assert decision["promotion_requirements"]["check_submission_ready_required"] is True
    assert decision["recommended_speed_patch_priority"][0] == "compact_tool_schema"


def test_consolidated_reports_link_correctness_efficiency_scorecard(tiny_project):
    _seed_scorecard_inputs(tiny_project.outputs_dir)
    run_correctness_efficiency_scorecard(tiny_project)
    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    system = json.loads((tiny_project.outputs_dir / "reports" / "system_summary.json").read_text(encoding="utf-8"))
    accuracy = json.loads((tiny_project.outputs_dir / "reports" / "accuracy_and_bottleneck_summary.json").read_text(encoding="utf-8"))

    assert "correctness_efficiency_evaluation" in index
    assert index["correctness_efficiency_evaluation"]["scorecard_path"] == "outputs/reports/correctness_efficiency_scorecard.md"
    assert system["correctness_efficiency_evaluation"]["decision"] == "speed_only_patch_needs_validation"
    assert accuracy["correctness_efficiency_evaluation"]["official_overall_score_claim"] is False

    combined = "\n".join(path.read_text(encoding="utf-8") for path in (tiny_project.outputs_dir / "reports").glob("correctness_efficiency*.json"))
    assert "Authorization" not in combined
    assert "Bearer " not in combined
    assert "client_secret" not in combined
    assert "abc***" not in combined
