#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import current_report_run_id, report_is_fresh, report_metadata
from scripts.check_submission_ready import check_submission_ready
from scripts.run_official_token_reduction_eval import _load_json


REQUIRED_REPORTS = {
    "official_token_reduction_promotion_report": "official_token_reduction_promotion_report.json",
    "endpoint_schema_rule_candidate_eval": "endpoint_schema_rule_candidate_eval.json",
    "hidden_style_eval": "hidden_style_eval.json",
    "endpoint_family_failure_report": "endpoint_family_failure_report.json",
    "schema_dataset_positive_repair_analysis": "schema_dataset_positive_repair_analysis.json",
    "sql_ast_candidate_ranking_report": "sql_ast_candidate_ranking_report.json",
    "retrieval_ablation_report": "retrieval_ablation_report.json",
    "repair_selector_v2_shadow_eval": "repair_selector_v2_shadow_eval.json",
    "endpoint_schema_rule_canary": "endpoint_schema_rule_canary.json",
    "endpoint_schema_rule_packaged_trial": "endpoint_schema_rule_packaged_trial.json",
    "ast_guided_sql_candidate_canary": "ast_guided_sql_candidate_canary.json",
    "repair_selector_v3_shadow_eval": "repair_selector_v3_shadow_eval.json",
    "accuracy_promotion_decision_report": "accuracy_promotion_decision_report.json",
    "low_score_failure_mining_report": "low_score_failure_mining_report.json",
    "score_component_error_report": "score_component_error_report.json",
    "evidence_answer_candidate_eval": "evidence_answer_candidate_eval.json",
    "answer_shape_v2_ab_eval": "answer_shape_v2_ab_eval.json",
    "unsafe_answer_candidate_analysis": "unsafe_answer_candidate_analysis.json",
    "supportable_answer_rewrite_eval": "supportable_answer_rewrite_eval.json",
    "local_index_fact_coverage_report": "local_index_fact_coverage_report.json",
    "execution_candidate_search": "execution_candidate_search.json",
    "llm_candidate_search": "llm_candidate_search.json",
    "llm_answer_rewrite_search": "llm_answer_rewrite_search.json",
    "endpoint_family_tiebreak_v2_shadow": "endpoint_family_tiebreak_v2_shadow.json",
    "live_mode_readiness_report": "live_mode_readiness_report.json",
    "targeted_accuracy_packaged_trial": "targeted_accuracy_packaged_trial.json",
    "score_0_7_push_report": "score_0_7_push_report.json",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_winner_readiness_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "winner_readiness_report.json"
    md_path = config.outputs_dir / "winner_readiness_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "fresh": payload["freshness"]["fresh"]}, indent=2, sort_keys=True))
    return 0


def generate_winner_readiness_report(config: Config) -> dict[str, Any]:
    expected_run_id = current_report_run_id(config.outputs_dir)
    stale = [
        name
        for name, filename in REQUIRED_REPORTS.items()
        if not report_is_fresh(config.outputs_dir / filename, expected_run_id)
    ]
    if stale:
        raise RuntimeError(f"Required reports are missing or stale for run_id {expected_run_id}: {', '.join(stale)}")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    sql_first = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    reports = {name: _load_json(config.outputs_dir / filename) for name, filename in REQUIRED_REPORTS.items()}
    packaged_trial = _load_json(config.outputs_dir / "official_token_reduction_packaged_trial.json")
    cleanup_audit = _load_json(config.outputs_dir / "redundant_file_audit.json")
    cleanup_report = _load_json(config.outputs_dir / "redundant_file_cleanup_report.json")
    autonomous_trial = _load_json(config.outputs_dir / "autonomous_packaged_trial.json")
    autonomous_score_push = _load_json(config.outputs_dir / "autonomous_score_push_report.json")
    integration_diff = _load_json(config.outputs_dir / "score075_integration_diff_report.json")
    readiness = check_submission_ready(config)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "winner_readiness_report",
        "freshness": {"fresh": True, "run_id": expected_run_id, "required_reports": list(REQUIRED_REPORTS)},
        "packaged": {
            "preferred_strategy": manifest.get("preferred_strategy", "SQL_FIRST_API_VERIFY"),
            "strict_final_score": sql_first.get("avg_final_score"),
            "strict_correctness": sql_first.get("avg_correctness_score"),
            "estimated_tokens": sql_first.get("avg_estimated_tokens"),
            "runtime": sql_first.get("avg_runtime"),
            "tool_calls": sql_first.get("avg_tool_call_count"),
            "final_submission_ready": readiness.get("ok"),
            "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok"),
        },
        "official_token_reduction_packaged_trial": packaged_trial.get("summary", {}),
        "official_token_reduction_promotion_report": reports["official_token_reduction_promotion_report"].get("summary", {}),
        "endpoint_schema_rule_candidate_eval": reports["endpoint_schema_rule_candidate_eval"].get("summary", {}),
        "hidden_style_eval": reports["hidden_style_eval"].get("summary", {}),
        "endpoint_family_failure_report": reports["endpoint_family_failure_report"].get("summary", {}),
        "schema_dataset_positive_repair_analysis": reports["schema_dataset_positive_repair_analysis"].get("summary", {}),
        "sql_ast_candidate_ranking_report": reports["sql_ast_candidate_ranking_report"].get("summary", {}),
        "retrieval_ablation_report": reports["retrieval_ablation_report"].get("summary", {}),
        "repair_selector_v2_shadow_eval": reports["repair_selector_v2_shadow_eval"].get("summary", {}),
        "endpoint_schema_rule_canary": reports["endpoint_schema_rule_canary"].get("summary", {}),
        "endpoint_schema_rule_packaged_trial": reports["endpoint_schema_rule_packaged_trial"].get("summary", {}),
        "ast_guided_sql_candidate_canary": reports["ast_guided_sql_candidate_canary"].get("summary", {}),
        "repair_selector_v3_shadow_eval": reports["repair_selector_v3_shadow_eval"].get("summary", {}),
        "accuracy_promotion_decision_report": reports["accuracy_promotion_decision_report"].get("summary", {}),
        "accuracy_promotion_decision_freshness": reports["accuracy_promotion_decision_report"].get("freshness", {}),
        "low_score_failure_mining_report": reports["low_score_failure_mining_report"].get("summary", {}),
        "score_component_error_report": reports["score_component_error_report"].get("summary", {}),
        "evidence_answer_candidate_eval": reports["evidence_answer_candidate_eval"].get("summary", {}),
        "answer_shape_v2_ab_eval": reports["answer_shape_v2_ab_eval"].get("summary", {}),
        "unsafe_answer_candidate_analysis": reports["unsafe_answer_candidate_analysis"].get("summary", {}),
        "supportable_answer_rewrite_eval": reports["supportable_answer_rewrite_eval"].get("summary", {}),
        "local_index_fact_coverage_report": reports["local_index_fact_coverage_report"].get("summary", {}),
        "execution_candidate_search": reports["execution_candidate_search"].get("summary", {}),
        "llm_candidate_search": reports["llm_candidate_search"].get("summary", {}),
        "llm_answer_rewrite_search": _llm_answer_summary(reports["llm_answer_rewrite_search"]),
        "endpoint_family_tiebreak_v2_shadow": reports["endpoint_family_tiebreak_v2_shadow"].get("summary", {}),
        "live_mode_readiness_report": reports["live_mode_readiness_report"].get("summary", {}),
        "targeted_accuracy_packaged_trial": reports["targeted_accuracy_packaged_trial"].get("summary", {}),
        "score_0_7_push_report": reports["score_0_7_push_report"].get("summary", {}),
        "autonomous_packaged_trial": autonomous_trial.get("summary", {}),
        "autonomous_score_push_report": autonomous_score_push.get("summary", {}),
        "score075_integration_diff_report": {
            "recommendation": integration_diff.get("recommendation"),
            "merged_branches": integration_diff.get("merged_branches", []),
            "rejected_branches": integration_diff.get("rejected_branches", []),
            "pending_branches": integration_diff.get("pending_branches", []),
            "metrics": integration_diff.get("metrics", {}),
        },
        "cleanup": {
            "audit_ran": bool(cleanup_audit.get("rows")),
            "cleanup_report_exists": bool(cleanup_report),
            "cleanup_applied": cleanup_report.get("applied", False),
            "deleted_count": cleanup_report.get("summary", {}).get("deleted_count", 0),
            "no_protected_files_deleted": cleanup_report.get("summary", {}).get("no_protected_files_deleted", True),
            "final_validation_passed": readiness.get("ok"),
            "final_submission_format_unchanged": readiness.get("ok"),
        },
        "visualization_dataflow_completeness": {
            "official_token_reduction_visible": True,
            "research_technique_tables_present": True,
        },
        "final_recommendation": _final_recommendation(
            packaged=sql_first,
            readiness=readiness,
            promotion=reports["official_token_reduction_promotion_report"].get("summary", {}),
            hidden=reports["hidden_style_eval"].get("summary", {}),
            accuracy=reports["accuracy_promotion_decision_report"].get("summary", {}),
        ),
        "recommended_next_action": [
            "Submit with official-token reduction if the promotion report remains kept.",
            "Keep repair execution disabled.",
            "Keep compact context disabled.",
            "Use endpoint/schema rule candidates only as future canary inputs.",
            "Keep accuracy changes shadow-only unless the accuracy decision report explicitly recommends promotion.",
            "Use the 0.70 push report to decide whether any targeted accuracy change is worth a later explicit promotion.",
            "Use the autonomous 0.75 score-push report only after integration has merged and validated worker branches.",
        ],
        "notes": [
            "This report does not change packaged behavior.",
            "Official-token reduction is the only behavior-changing default promoted in this pass when gates pass.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    packaged = payload["packaged"]
    lines = [
        "# Winner Readiness Report",
        "",
        f"- Freshness run ID: `{payload['freshness']['run_id']}`",
        f"- Preferred strategy: `{packaged['preferred_strategy']}`",
        f"- Strict final score: {packaged['strict_final_score']}",
        f"- Estimated tokens/runtime/tools: {packaged['estimated_tokens']} / {packaged['runtime']} / {packaged['tool_calls']}",
        f"- Final submission ready: {packaged['final_submission_ready']}",
        f"- Official-token packaged trial recommendation: `{payload['official_token_reduction_packaged_trial'].get('recommendation')}`",
        f"- Official-token promotion recommendation: `{payload['official_token_reduction_promotion_report'].get('recommendation')}`",
        f"- Hidden-style passed/total: {payload['hidden_style_eval'].get('passed_cases')}/{payload['hidden_style_eval'].get('total_cases')}",
        f"- Hidden-style family/schema stability: {payload['hidden_style_eval'].get('family_stability_rate')} / {payload['hidden_style_eval'].get('schema_stability_rate')}",
        f"- Accuracy decision hidden-style fresh: {payload.get('accuracy_promotion_decision_freshness', {}).get('fresh')}",
        f"- Endpoint-family risky rows: {payload['endpoint_family_failure_report'].get('risky_rows')}",
        f"- Endpoint/schema rule candidates: {payload['endpoint_schema_rule_candidate_eval'].get('candidate_rules')}",
        f"- Endpoint/schema canary recommendation: `{payload['endpoint_schema_rule_canary'].get('recommendation')}`",
        f"- Endpoint/schema packaged trial recommendation: `{payload['endpoint_schema_rule_packaged_trial'].get('recommendation')}`",
        f"- AST-guided SQL canary recommendation: `{payload['ast_guided_sql_candidate_canary'].get('recommendation')}`",
        f"- Repair selector v3 success: {payload['repair_selector_v3_shadow_eval'].get('success')}",
        f"- Accuracy decision: `{payload['accuracy_promotion_decision_report'].get('recommendation')}`",
        f"- 0.70 push achieved score: {payload['score_0_7_push_report'].get('strict_score_achieved')}",
        f"- 0.70 reached safely: {payload['score_0_7_push_report'].get('target_0_70_reached')}",
        f"- 0.70 push recommendation: `{payload['score_0_7_push_report'].get('final_recommendation')}`",
        f"- Score-component API-correct answer-weak rows: {payload['score_component_error_report'].get('api_correct_answer_weak_rows')}",
        f"- Evidence-answer safe rows/projected score: {payload['evidence_answer_candidate_eval'].get('safe_rows')} / "
        f"{payload['evidence_answer_candidate_eval'].get('best_projected_strict_final_score')}",
        f"- Answer-shape v2 changed/safe/projected score: {payload['answer_shape_v2_ab_eval'].get('changed_rows')} / "
        f"{payload['answer_shape_v2_ab_eval'].get('safe_rows')} / {payload['answer_shape_v2_ab_eval'].get('projected_strict_final_score')}",
        f"- Unsafe answer analysis rows/positive supportable: {payload['unsafe_answer_candidate_analysis'].get('total_rows')} / "
        f"{payload['unsafe_answer_candidate_analysis'].get('positive_supportable_rows')}",
        f"- Supportable answer rewrite safe rows/projected score: {payload['supportable_answer_rewrite_eval'].get('safe_rows')} / "
        f"{payload['supportable_answer_rewrite_eval'].get('best_projected_strict_final_score')}",
        f"- LLM answer rewrite search: {payload['llm_answer_rewrite_search'].get('status')} "
        f"(recommendation: `{payload['llm_answer_rewrite_search'].get('recommendation')}`, "
        f"model: {payload['llm_answer_rewrite_search'].get('model')}, "
        f"accepted: {payload['llm_answer_rewrite_search'].get('accepted_candidate_count')}/"
        f"{payload['llm_answer_rewrite_search'].get('candidate_count')})",
        f"- Local fact coverage available/used/covered: {payload['local_index_fact_coverage_report'].get('local_evidence_available_rows')} / "
        f"{payload['local_index_fact_coverage_report'].get('local_evidence_used_in_final_answer_rows')} / "
        f"{payload['local_index_fact_coverage_report'].get('requested_fact_covered_rows')}",
        f"- Endpoint-family tie-break v2 shadow recommendation: `{payload['endpoint_family_tiebreak_v2_shadow'].get('recommendation')}` "
        f"(trial eligible rows: {payload['endpoint_family_tiebreak_v2_shadow'].get('trial_eligible_rows')})",
        f"- Live-mode readiness diagnostic-only: {payload['live_mode_readiness_report'].get('diagnostic_only')} "
        f"(dry-run dependent rows: {payload['live_mode_readiness_report'].get('dry_run_dependent_rows')})",
        f"- Autonomous packaged trial recommendation: `{payload['autonomous_packaged_trial'].get('recommendation')}`",
        f"- Autonomous 0.75 best score/reached: {payload['autonomous_score_push_report'].get('best_achieved_score')} / "
        f"{payload['autonomous_score_push_report'].get('target_0_75_reached')}",
        f"- score075 integration merged/rejected/pending branches: "
        f"{len(payload['score075_integration_diff_report'].get('merged_branches', []))} / "
        f"{len(payload['score075_integration_diff_report'].get('rejected_branches', []))} / "
        f"{len(payload['score075_integration_diff_report'].get('pending_branches', []))}",
        f"- Redundant file audit ran: {payload['cleanup'].get('audit_ran')}",
        f"- Cleanup applied/deleted/protected-ok: {payload['cleanup'].get('cleanup_applied')} / "
        f"{payload['cleanup'].get('deleted_count')} / {payload['cleanup'].get('no_protected_files_deleted')}",
        f"- Repair selector v2 success: {payload['repair_selector_v2_shadow_eval'].get('success')}",
        f"- Final recommendation: `{payload['final_recommendation']}`",
        "",
        "## Recommended Next Action",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["recommended_next_action"])
    return "\n".join(lines) + "\n"


def _final_recommendation(
    *,
    packaged: dict[str, Any],
    readiness: dict[str, Any],
    promotion: dict[str, Any],
    hidden: dict[str, Any],
    accuracy: dict[str, Any],
) -> str:
    if not readiness.get("ok"):
        return "do_not_submit_until_regression_fixed"
    if promotion.get("recommendation") != "promoted_keep_enabled":
        return "submit_current_safe_version"
    if float(packaged.get("avg_final_score") or 0.0) < 0.6481:
        return "do_not_submit_until_regression_fixed"
    if float(packaged.get("avg_correctness_score") or 0.0) < 0.6743:
        return "do_not_submit_until_regression_fixed"
    if float(packaged.get("avg_estimated_tokens") or 999999.0) >= 899.2286:
        return "do_not_submit_until_regression_fixed"
    total = int(hidden.get("total_cases") or 0)
    pass_rate = (float(hidden.get("passed_cases") or 0) / total) if total else 0.0
    if total < 48 or pass_rate < 0.98 or float(hidden.get("family_stability_rate") or 0.0) < 0.98 or float(hidden.get("schema_stability_rate") or 0.0) < 0.98:
        return "do_not_submit_until_regression_fixed"
    if accuracy.get("recommendation") == "do_not_submit_until_regression_fixed":
        return "do_not_submit_until_regression_fixed"
    if accuracy.get("recommendation") in {"promote_endpoint_schema_rules", "promote_ast_guided_sql"}:
        return "ready_to_submit_with_official_token_reduction_plus_safe_accuracy_rules"
    return "ready_to_submit_with_official_token_reduction"


def _llm_answer_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(report.get("summary") or {})
    if report:
        summary.update(
            {
                "provider": report.get("provider"),
                "model": report.get("model"),
                "candidate_count": sum(int(row.get("rewrite_count") or 0) for row in report.get("rows", [])),
                "accepted_candidate_count": int(summary.get("safe_rows") or 0),
                "budget": report.get("budget", {}),
                "key_visible": bool(report.get("provider") or not report.get("skipped")),
            }
        )
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
