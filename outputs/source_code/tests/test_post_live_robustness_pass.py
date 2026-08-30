from __future__ import annotations

import json

from scripts.run_integrated_robustness_gate import run_integrated_robustness_gate
from scripts.run_live_api_arbitration_regression_guard import run_live_api_arbitration_regression_guard
from scripts.run_live_tool_efficiency_audit import run_live_tool_efficiency_audit
from scripts.run_post_live_robustness_preflight import run_post_live_robustness_preflight


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_post_live_preflight_records_live_regression_context(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    _write_json(
        tiny_project.outputs_dir / "eval_results_strict.json",
        {"summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6554}}}},
    )
    _write_json(
        tiny_project.outputs_dir / "hidden_style_eval.json",
        {"summary": {"passed_cases": 48, "total_cases": 48, "failed_cases": 0}},
    )
    _write_json(reports / "live_api_readiness_smoke.json", {"outcome_counts": {"live_success": 10, "live_empty": 5}})
    _write_json(
        reports / "live_api_score_regression_baseline.json",
        {"baseline": {"strict_score": 0.6553}, "live": {"strict_score": 0.6247}, "delta": -0.0306},
    )
    _write_json(
        reports / "live_api_evidence_arbitration_trial.json",
        {"recommended_variant": "sql_primary_when_complete", "promotion_decision": "promote_arbitration_policy"},
    )
    _write_json(
        reports / "sql_template_coverage_audit.json",
        {"row_count": 285, "template_hit_count": 102, "template_miss_count": 183},
    )

    report = run_post_live_robustness_preflight(tiny_project)

    assert report["report_type"] == "post_live_robustness_preflight"
    assert report["current_score"] == 0.6554
    assert report["previous_baseline_score"] == 0.6553
    assert report["initial_live_regression_score"] == 0.6247
    assert report["active_arbitration_policy"] == "sql_primary_when_complete"
    assert "template dependency" in " ".join(report["known_risks"])


def test_arbitration_regression_guard_flags_live_empty_sql_override(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    _write_json(
        reports / "live_api_score_regression_analysis.json",
        {
            "rows": [
                {
                    "query_id": "q1",
                    "whether_sql_already_fully_answered": True,
                    "whether_live_api_was_necessary": False,
                    "live_api_state": "live_empty",
                    "whether_live_api_changed_evidence_priority": True,
                    "whether_answer_added_unnecessary_live_api_details": True,
                    "whether_live_api_contradicted_sql": False,
                }
            ]
        },
    )

    report = run_live_api_arbitration_regression_guard(tiny_project)

    assert report["report_type"] == "live_api_arbitration_regression_guard"
    assert report["policy_safe_to_keep"] is False
    assert report["policy_violation_count"] == 2
    assert {item["violation_type"] for item in report["policy_violations"]} >= {
        "live_empty_overrode_sql",
        "noisy_verification_added",
    }


def test_live_tool_efficiency_audit_keeps_diagnostic_only(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    _write_json(
        tiny_project.outputs_dir / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_final_score": 0.6554,
                        "avg_tool_call_count": 1.4,
                        "avg_runtime": 0.5,
                        "avg_estimated_tokens": 1000,
                    }
                }
            },
            "rows": [
                {"strategy": "SQL_FIRST_API_VERIFY", "tool_call_count": 2, "runtime": 0.4, "estimated_tokens": 1000}
            ],
        },
    )
    _write_json(
        reports / "full_generated_prompt_suite_diagnostic.json",
        {"rows": [{"api_calls": 1, "sql_calls": 1, "failure_category": "ok"}]},
    )

    report = run_live_tool_efficiency_audit(tiny_project)

    assert report["report_type"] == "live_tool_efficiency_audit"
    assert report["diagnostic_only"] is True
    assert report["live_mode"]["avg_tool_call_count"] == 1.4
    assert report["generated_prompt_diagnostic_mode"]["prompt_count"] == 1


def test_integrated_robustness_gate_recommends_arbitration_only_when_schema_trial_fails(tiny_project, monkeypatch):
    reports = tiny_project.outputs_dir / "reports"
    _write_json(
        tiny_project.outputs_dir / "eval_results_strict.json",
        {"summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6554}}}},
    )
    _write_json(
        tiny_project.outputs_dir / "hidden_style_eval.json",
        {"summary": {"passed_cases": 48, "total_cases": 48, "failed_cases": 0}},
    )
    _write_json(reports / "live_api_readiness_smoke.json", {"outcome_counts": {"live_success": 10, "live_empty": 5}})
    _write_json(
        reports / "nl_sql_robustness_audit.json",
        {"metrics": {"template_dependency_score": 0.66, "paraphrase_consistency_score": 0.72}},
    )
    _write_json(
        reports / "schema_aware_sql_feedback_loop.json",
        {"promotion_decision": {"decision": "keep_trial_only"}},
    )
    _write_json(
        reports / "live_api_evidence_arbitration_trial.json",
        {"promotion_decision": "promote_arbitration_policy"},
    )
    monkeypatch.setattr(
        "scripts.run_integrated_robustness_gate.check_submission_ready",
        lambda config: {"ok": True, "default_strategy_is_sql_first_api_verify": True},
    )

    report = run_integrated_robustness_gate(tiny_project)

    assert report["report_type"] == "integrated_robustness_gate"
    assert report["recommendation"] == "promote_arbitration_policy_only"
    assert report["promotion_allowed"] is True
    assert report["gates"]["schema_aware_not_promoted"]["passed"] is True
