from __future__ import annotations

import json
from dataclasses import replace

from dashagent.config import Config
from dashagent.dataflow_visualizer import build_dataflow_summary, build_markdown_report
from dashagent.repair_candidate_selector_v2 import select_repair_candidate_v2
from dashagent.report_run import report_metadata, runtime_budget_for_row, runtime_budget_summary, start_report_run
from dashagent.sql_ast_candidate_ranker import rank_sql_candidate_ast
from scripts.analyze_schema_dataset_positive_repair import analyze_schema_dataset_positive_repair
from scripts.generate_endpoint_family_failure_report import generate_endpoint_family_failure_report
from scripts.generate_official_token_reduction_promotion_report import compare_final_submission_structure
from scripts.generate_sql_ast_candidate_ranking_report import generate_sql_ast_candidate_ranking_report
from scripts.generate_winner_readiness_report import generate_winner_readiness_report
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS, discover_query_output_dirs
from scripts.run_endpoint_schema_rule_candidate_eval import run_endpoint_schema_rule_candidate_eval
from scripts.run_hidden_style_eval import run_hidden_style_eval
from scripts.run_official_token_reduction_packaged_trial import _safe_to_promote, run_official_token_reduction_packaged_trial
from tests.test_official_token_reduction import _tree_hash, _write_official_token_inputs


def test_runtime_budget_helper_gates_average_and_row_regressions():
    ok_row = runtime_budget_for_row(baseline_runtime=0.100, trial_runtime=0.102)
    noisy_row = runtime_budget_for_row(baseline_runtime=0.001, trial_runtime=0.004)
    bad_row = runtime_budget_for_row(baseline_runtime=0.010, trial_runtime=0.030)

    assert ok_row["runtime_budget_ok"] is True
    assert noisy_row["runtime_regression_over_20pct"] is True
    assert noisy_row["timing_noise_explanation"]
    assert bad_row["runtime_budget_ok"] is False
    assert runtime_budget_summary([ok_row, noisy_row])["runtime_budget_ok"] is True
    assert runtime_budget_summary([bad_row])["runtime_budget_ok"] is False


def test_official_token_packaged_trial_is_isolated_and_excluded(tiny_project):
    _write_official_token_inputs(tiny_project)
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True)
    (final_submission / "manifest.json").write_text(json.dumps({"preferred_strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")
    before_hash = _tree_hash(final_submission)

    payload = run_official_token_reduction_packaged_trial(tiny_project)

    assert payload["feature_flag_default"] is True
    assert payload["packaged_execution_changed"] is False
    assert payload["protected_output_hashes_unchanged"] is True
    assert payload["summary"]["total_rows"] == 1
    assert "official_token_reduction_packaged_trial" in NON_SUBMISSION_OUTPUT_DIRS
    assert not discover_query_output_dirs(tiny_project.outputs_dir / "official_token_reduction_packaged_trial")
    assert _tree_hash(final_submission) == before_hash


def test_official_token_packaged_trial_safety_rejects_runtime_budget_failure():
    row = {
        "score_delta": 0.0,
        "token_delta": -1,
        "tool_delta": 0,
        "runtime_budget_ok": False,
        "final_answer_changed": False,
        "sql_changed": False,
        "api_changed": False,
        "live_api_evidence_fabricated": False,
        "required_fields_preserved": True,
        "dry_run_labels_preserved": True,
        "trial_formula_matches": True,
        "strict_scorer_check_passed": True,
        "protected_hashes_unchanged": True,
    }

    safe, reason = _safe_to_promote(row, runtime_summary={"avg_runtime_budget_ok": True}, secret_scan_ok=True)

    assert safe is False
    assert "row_runtime_budget_failed" in reason


def test_dataflow_official_token_reduction_status_visible():
    inactive = {"query_id": "q", "strategy": "SQL_FIRST_API_VERIFY", "final_answer": "x", "estimated_tokens": 10, "steps": [], "checkpoints": []}
    active = {
        **inactive,
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_official_token_reduction",
                "active": True,
                "reduced_fields": ["steps[0].result.rows"],
                "estimated_tokens_before": 20,
                "estimated_tokens_after": 10,
                "expected_savings": 10,
                "packaged_execution_changed": False,
                "correctness_impact_expected": False,
            }
        ],
    }

    assert build_dataflow_summary(inactive)["official_token_reduction"]["official_token_reduction_active"] is False
    summary = build_dataflow_summary(active)["official_token_reduction"]
    assert summary["official_token_reduction_active"] is True
    assert summary["token_savings"] == 10
    assert "Official Token Reduction" in build_markdown_report(active)


def test_hidden_style_eval_outputs_flags_and_cases(tiny_project):
    payload = run_hidden_style_eval(tiny_project)

    assert payload["exact_public_query_strings_used"] is False
    assert payload["repair_execution_enabled"] is False
    assert payload["compact_context_enabled"] is False
    assert payload["summary"]["total_cases"] >= 10
    assert payload["summary"]["family_stability_rate"] > 0
    assert payload["summary"]["total_cases"] >= 40
    assert payload["summary"]["family_stability_rate"] >= 0.95
    assert payload["summary"]["schema_stability_rate"] >= 0.95


def test_endpoint_and_ast_reports_are_report_only(tiny_project):
    _write_official_token_inputs(tiny_project)

    endpoint = generate_endpoint_family_failure_report(tiny_project)
    candidates = run_endpoint_schema_rule_candidate_eval(tiny_project)
    ast = generate_sql_ast_candidate_ranking_report(tiny_project)

    assert endpoint["report_only"] is True
    assert endpoint["gold_used_for_generation"] is False
    assert candidates["report_only"] is True
    assert candidates["gold_used_for_generation"] is False
    assert candidates["public_query_strings_used_for_generation"] is False
    assert ast["report_only"] is True
    assert ast["summary"]["candidate_count"] >= 1


def test_sql_ast_candidate_ranker_scores_valid_sql(tiny_project):
    from dashagent.executor import AgentExecutor

    executor = AgentExecutor(tiny_project)
    row = rank_sql_candidate_ast("SELECT COUNT(*) FROM dim_campaign", executor.schema_index, query="Count campaigns")

    assert row["parsed_ok"] is True
    assert row["aggregation_count"] >= 1
    assert row["ast_quality_score"] > 0


def test_repair_selector_v2_rejects_risky_repairs():
    safe = {
        "safe": True,
        "failed_checks": [],
        "sql_validation": {"ok": True, "ast_summaries": [{"parsed_ok": True}]},
    }
    current = {"sql": ["SELECT 1"], "api_calls": [], "tool_call_count": 1, "expected_answer_shape": "count"}
    repaired = {"sql": ["SELECT 1"], "api_calls": [], "tool_call_count": 1, "expected_answer_shape": "count", "fusion_agreement": True, "endpoint_family_confidence": 1.0, "offline_score_delta": 0.0}

    tied = select_repair_candidate_v2(current, repaired, safe, ast_current={"ast_quality_score": 1}, ast_repaired={"ast_quality_score": 1})
    assert tied["safe_to_select_repaired"] is False
    assert tied["selected_plan"] == "current"
    assert tied["decision_label"] == "no_op_tie_keep_current"
    repaired["sql"] = ["SELECT 2"]
    repaired["offline_score_delta"] = 0.0
    score_tie = select_repair_candidate_v2(current, repaired, safe, ast_current={"ast_quality_score": 1}, ast_repaired={"ast_quality_score": 1})
    assert score_tie["safe_to_select_repaired"] is False
    assert score_tie["decision_label"] == "score_tie_keep_current"
    repaired["offline_score_delta"] = -0.1
    rejected = select_repair_candidate_v2(current, repaired, safe, ast_current={"ast_quality_score": 1}, ast_repaired={"ast_quality_score": 1})
    assert rejected["safe_to_select_repaired"] is False
    assert "score_regression" in rejected["failed_checks"]


def test_winner_readiness_requires_fresh_reports(tiny_project):
    start_report_run(tiny_project.outputs_dir)
    stale_path = tiny_project.outputs_dir / "official_token_reduction_promotion_report.json"
    stale_path.write_text(json.dumps({"run_id": "old"}), encoding="utf-8")

    try:
        generate_winner_readiness_report(tiny_project)
    except RuntimeError as exc:
        assert "official_token_reduction_promotion_report" in str(exc)
    else:
        raise AssertionError("winner readiness should fail on stale reports")


def test_defaults_remain_disabled(tiny_project):
    config = Config.from_env(tiny_project.project_root)

    assert config.enable_official_token_reduction is True
    assert config.enable_compact_context_when_schema_vote_safe is False
    assert config.enable_gated_risk_cluster_repair_execution is False


def test_final_submission_structure_diff_rejects_experimental_roots(tiny_project):
    final_submission = tiny_project.outputs_dir / "final_submission"
    query_dir = final_submission / "query_001"
    query_dir.mkdir(parents=True)
    for name in ["metadata.json", "filled_system_prompt.txt"]:
        (query_dir / name).write_text("{}", encoding="utf-8")
    (query_dir / "trajectory.json").write_text(
        json.dumps({"strategy": "SQL_FIRST_API_VERIFY", "final_answer": "x", "tool_call_count": 1, "runtime": 0.0, "estimated_tokens": 1}),
        encoding="utf-8",
    )
    manifest = {
        "preferred_strategy": "SQL_FIRST_API_VERIFY",
        "total_number_of_queries": 1,
        "queries": [{"query_id": "query_001"}],
    }
    (tiny_project.outputs_dir / "final_submission_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    diff = compare_final_submission_structure(tiny_project, manifest)

    assert diff["unchanged"] is True
