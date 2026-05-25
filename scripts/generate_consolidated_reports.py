#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORTS_DIRNAME = "reports"

POST_CHANGE_VALIDATION_COMMANDS = [
    "python3 -m pytest -q",
    "python3 scripts/audit_dashsys_project_skill.py",
    "python3 scripts/generate_end_to_end_system_dataflow.py",
    "python3 scripts/audit_workshop_requirements.py",
    "python3 scripts/run_dev_eval.py --strict",
    "python3 scripts/run_hidden_style_eval.py",
    "python3 scripts/audit_live_adobe_api_readiness.py",
    "python3 scripts/generate_api_required_readiness_matrix.py",
    "python3 scripts/run_live_api_readiness_smoke.py",
    "python3 scripts/run_live_api_evidence_pipeline_trial.py",
    "python3 scripts/run_mock_live_api_evidence_pipeline_trial.py",
    "python3 scripts/run_evidence_usage_audit.py",
    "python3 scripts/run_evidence_aware_answer_rewrite_trial.py",
    "python3 scripts/run_sql_evidence_usage_audit.py",
    "python3 scripts/run_score_path_contribution_audit.py",
    "python3 scripts/run_score_focused_core_improvement_trials.py",
    "python3 scripts/run_comprehensive_failure_analysis.py",
    "python3 scripts/run_deterministic_prompt_type_audit.py",
    "python3 scripts/run_type_specific_deterministic_rule_trials.py",
    "python3 scripts/run_sdk_tool_calling_optimization_audit.py",
    "python3 scripts/run_sdk_tool_calling_optimization_trials.py",
    "python3 scripts/run_correctness_efficiency_scorecard.py",
    "python3 scripts/run_sdk_tool_calling_efficiency_promotion.py --validation-complete",
    "python3 scripts/run_tool_calling_policy_optimizer.py",
    "python3 scripts/run_core_tool_optimization_audit.py",
    "python3 scripts/run_core_tool_policy_optimizer.py",
    "python3 scripts/audit_repo_cleanup_candidates.py",
    "python3 scripts/run_confidence_calibration_audit.py",
    "python3 scripts/run_token_efficiency_audit.py",
    "python3 scripts/check_llm_sdk_backend.py",
    "python3 scripts/run_workflow_decision_audit.py",
    "python3 scripts/run_decision_feedback_loop.py",
    "python3 scripts/run_llm_baseline_eval.py",
    "python3 scripts/run_llm_strict_baseline_eval.py",
    "python3 scripts/run_llm_hidden_style_diagnostic.py",
    "python3 scripts/generate_winner_readiness_report.py",
    "python3 scripts/generate_research_inspired_report.py",
    "python3 scripts/generate_system_status_dashboard.py",
    "python3 scripts/generate_technique_visual_cards.py",
    "python3 scripts/generate_project_mermaid_visualizations.py",
    "python3 scripts/generate_full_project_dataflow_svg.py",
    "python3 scripts/generate_visualization_index.py",
    "python3 scripts/package_submission.py",
    "python3 scripts/package_query_outputs.py",
    "python3 scripts/check_submission_ready.py",
]

REPORT_REGENERATION_TARGETS = [
    "outputs/reports/report_index.md/json",
    "outputs/reports/system_summary.md/json",
    "outputs/reports/llm_baseline_summary.md/json",
    "outputs/reports/accuracy_and_bottleneck_summary.md/json",
    "outputs/reports/visualization_summary.md/json",
    "outputs/reports/workshop_requirement_audit.md/json",
    "outputs/reports/live_adobe_api_readiness_audit.md/json",
    "outputs/reports/api_required_readiness_matrix.md/json",
    "outputs/reports/live_api_readiness_smoke.md/json",
    "outputs/reports/context7_docs_audit_preflight.md/json",
    "outputs/reports/context7_dependency_docs_summary.md/json",
    "outputs/reports/context7_code_alignment_audit.md/json",
    "outputs/reports/context7_fix_decision.md/json",
    "outputs/reports/live_api_evidence_pipeline_trial.md/json",
    "outputs/reports/mock_live_api_evidence_pipeline_trial.md/json",
    "outputs/reports/post_live_robustness_preflight.md/json",
    "outputs/reports/live_api_arbitration_regression_guard.md/json",
    "outputs/reports/full_generated_prompt_suite_diagnostic.md/json",
    "outputs/reports/nl_sql_robustness_audit.md/json",
    "outputs/reports/nl_sql_paraphrase_consistency.md/json",
    "outputs/reports/schema_aware_sql_failure_decomposition.md/json",
    "outputs/reports/schema_aware_sql_feedback_loop.md/json",
    "outputs/reports/llm_agent_trace_decomposition.md/json",
    "outputs/reports/controller_rewrite_policy_trial.md/json",
    "outputs/reports/multi_llm_backend_robustness.md/json",
    "outputs/reports/live_tool_efficiency_audit.md/json",
    "outputs/reports/integrated_robustness_gate.md/json",
    "outputs/reports/evidence_usage_audit.md/json",
    "outputs/reports/evidence_aware_answer_rewrite_trial.md/json",
    "outputs/reports/feedback_loop_answer_synthesis_final.md/json",
    "outputs/reports/sql_evidence_usage_audit.md/json",
    "outputs/reports/score_path_contribution_audit.md/json",
    "outputs/reports/score_focused_core_improvement_trials.md/json",
    "outputs/reports/score_focused_core_fix_decision.md/json",
    "outputs/reports/comprehensive_failure_analysis_preflight.md/json",
    "outputs/reports/official_row_failure_table.md/json",
    "outputs/reports/generated_prompt_failure_table.md/json",
    "outputs/reports/cross_dataset_failure_clusters.md/json",
    "outputs/reports/general_deterministic_rule_candidates.md/json",
    "outputs/reports/cross_dataset_counterfactual_answer_sketches.md/json",
    "outputs/reports/general_rule_hardcoding_risk_audit.md/json",
    "outputs/reports/comprehensive_failure_fix_decision.md/json",
    "outputs/reports/deterministic_prompt_type_audit.md/json",
    "outputs/reports/type_specific_deterministic_rule_candidates.md/json",
    "outputs/reports/type_specific_deterministic_rule_trials.md/json",
    "outputs/reports/type_specific_rule_fix_decision.md/json",
    "outputs/reports/sdk_tool_calling_optimization_preflight.md/json",
    "outputs/reports/sdk_tool_call_surface_audit.md/json",
    "outputs/reports/sdk_tool_call_decision_analysis.md/json",
    "outputs/reports/sdk_tool_call_optimization_variants.md/json",
    "outputs/reports/sdk_tool_calling_optimization_trials.md/json",
    "outputs/reports/sdk_tool_calling_fix_decision.md/json",
    "outputs/reports/correctness_efficiency_scorecard.md/json",
    "outputs/reports/correctness_efficiency_fix_decision.md/json",
    "outputs/reports/sdk_tool_calling_promotion_preflight.md/json",
    "outputs/reports/sdk_tool_calling_promotion_plan.md/json",
    "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md/json",
    "outputs/reports/tool_calling_policy_optimizer.md/json",
    "outputs/reports/tool_calling_objective_functions.md/json",
    "outputs/reports/tool_calling_policy_search_results.md/json",
    "outputs/reports/tool_calling_compiled_policy_candidate.md/json",
    "outputs/reports/tool_calling_policy_promotion_decision.md/json",
    "outputs/reports/core_tool_optimization_audit.md/json",
    "outputs/reports/core_tool_optimization_search_space.md/json",
    "outputs/reports/core_tool_policy_optimizer.md/json",
    "outputs/reports/core_tool_policy_search_results.md/json",
    "outputs/reports/execute_sql_optimization_candidates.md/json",
    "outputs/reports/call_api_optimization_candidates.md/json",
    "outputs/reports/core_tool_compiled_policy_candidate.md/json",
    "outputs/reports/core_tool_policy_promotion_decision.md/json",
    "outputs/reports/repo_cleanup_preflight.md/json",
    "outputs/reports/repo_cleanup_candidate_inventory.md/json",
    "outputs/reports/repo_cleanup_deletion_plan.md/json",
    "outputs/reports/repo_cleanup_result.md/json",
    "outputs/reports/dashsys_project_skill_audit.md/json",
    "outputs/reports/confidence_calibration_audit.md/json",
    "outputs/reports/token_efficiency_audit.md/json",
    "outputs/reports/workflow_decision_map.md/json",
    "outputs/reports/workflow_decision_audit.md/json",
    "outputs/reports/improvement_feedback_loop_index.md/json",
    "outputs/reports/feedback_loop_semantic_router_final.md/json",
    "outputs/reports/decision_stage_improvement_summary.md/json",
    "outputs/reports/cleanup_audit.md/json",
    "outputs/reports/cleanup_final_report.md/json",
    "outputs/winner_readiness_report.md/json",
    "outputs/final_research_inspired_improvement_report.md/json",
    "outputs/visualizations/end_to_end_system_dataflow.html",
    "outputs/visualizations/end_to_end_system_dataflow.md/json",
    "outputs/visualizations/project_architecture_c4.md/mmd",
    "outputs/visualizations/end_to_end_pipeline_mermaid.md/mmd",
    "outputs/visualizations/live_adobe_api_status_mermaid.md/mmd",
    "outputs/visualizations/report_generation_map.md/mmd",
    "outputs/visualizations/full_project_dataflow.svg",
    "outputs/visualizations/full_project_dataflow.md/json",
    "outputs/reports/full_project_dataflow_svg_audit.md/json",
    "outputs/visualizations/index.md/json",
    "outputs/visualizations/system_status_dashboard.md/json",
    "outputs/visualizations/technique_visual_cards.md/json",
    "outputs/reports/visualization_sync_audit.md/json",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_consolidated_reports(config)
    print(json.dumps({"reports_dir": str(config.outputs_dir / REPORTS_DIRNAME), "files": payload["written_files"]}, indent=2, sort_keys=True))
    return 0


def generate_consolidated_reports(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / REPORTS_DIRNAME
    reports_dir.mkdir(parents=True, exist_ok=True)
    _maybe_generate_end_to_end_system_dataflow(config)
    _maybe_generate_project_mermaid_visualizations(config)
    _maybe_generate_full_project_dataflow_svg(config)

    sources = _load_sources(config)
    system = build_system_summary(config, sources)
    llm = build_llm_baseline_summary(config, sources)
    accuracy = build_accuracy_and_bottleneck_summary(config, sources)
    visualization = build_visualization_summary(config, sources)
    index = build_report_index(config, system, llm, accuracy, visualization)

    written = []
    for stem, payload, markdown in [
        ("system_summary", system, render_system_summary(system)),
        ("llm_baseline_summary", llm, render_llm_summary(llm)),
        ("accuracy_and_bottleneck_summary", accuracy, render_accuracy_summary(accuracy)),
        ("visualization_summary", visualization, render_visualization_summary(visualization)),
        ("report_index", index, render_report_index(index)),
    ]:
        json_path = reports_dir / f"{stem}.json"
        md_path = reports_dir / f"{stem}.md"
        safe_payload = _safe_payload(payload)
        json_path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        written.extend([_rel(config, json_path), _rel(config, md_path)])
    return {"written_files": written, "reports_dir": _rel(config, reports_dir)}


def _load_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    visualizations = outputs / "visualizations"
    return {
        "eval_results_strict": _load_json(outputs / "eval_results_strict.json"),
        "winner_readiness": _load_json(outputs / "winner_readiness_report.json"),
        "hidden_style": _load_json(outputs / "hidden_style_eval.json"),
        "official_token_reduction": _load_json(outputs / "official_token_reduction_promotion_report.json"),
        "autonomous_trial": _load_json(outputs / "autonomous_packaged_trial.json"),
        "autonomous_score_push": _load_json(outputs / "autonomous_score_push_report.json"),
        "score075_blocker": _load_json(outputs / "score075_blocker_analysis.json"),
        "answer_shape_v2": _load_json(outputs / "answer_shape_v2_ab_eval.json"),
        "supportable_rewrite": _load_json(outputs / "supportable_answer_rewrite_eval.json"),
        "llm_answer_rewrite": _load_json(outputs / "llm_answer_rewrite_search.json"),
        "endpoint_tiebreak": _load_json(outputs / "endpoint_family_tiebreak_v2_shadow.json"),
        "endpoint_schema_canary": _load_json(outputs / "endpoint_schema_rule_canary.json"),
        "ast_canary": _load_json(outputs / "ast_guided_sql_candidate_canary.json"),
        "live_readiness": _load_json(outputs / "live_mode_readiness_report.json"),
        "live_adobe_api_readiness": _load_json(outputs / "reports" / "live_adobe_api_readiness_audit.json"),
        "api_required_readiness_matrix": _load_json(outputs / "reports" / "api_required_readiness_matrix.json"),
        "live_api_smoke": _load_json(outputs / "reports" / "live_api_readiness_smoke.json"),
        "live_api_endpoint_path_diagnosis": _load_json(outputs / "reports" / "live_api_endpoint_path_diagnosis.json"),
        "live_api_external_blockers": _load_json(outputs / "reports" / "live_api_external_blockers.json"),
        "live_api_endpoint_followup_commands": _load_json(outputs / "reports" / "live_api_endpoint_followup_commands.json"),
        "live_api_full_run_blocker": _load_json(outputs / "reports" / "live_api_full_run_blocker.json"),
        "post_permission_live_api_verification": _load_json(outputs / "reports" / "post_permission_live_api_verification.json"),
        "adobe_access_waiting_status": _load_json(outputs / "reports" / "adobe_access_waiting_status.json"),
        "live_api_safe_get_endpoint_matrix": _load_json(outputs / "reports" / "live_api_safe_get_endpoint_matrix.json"),
        "live_api_remaining_endpoint_resolution": _load_json(outputs / "reports" / "live_api_remaining_endpoint_resolution_summary.json"),
        "guarded_dash_agent_live_e2e_trial": _load_json(outputs / "reports" / "guarded_dash_agent_live_e2e_trial.json"),
        "live_api_post_exact_go_no_go": _load_json(outputs / "reports" / "live_api_post_exact_reproduction_go_no_go.json"),
        "live_api_pipeline_trial": _load_json(outputs / "reports" / "live_api_evidence_pipeline_trial.json"),
        "mock_live_api_pipeline_trial": _load_json(outputs / "reports" / "mock_live_api_evidence_pipeline_trial.json"),
        "post_live_robustness_preflight": _load_json(outputs / "reports" / "post_live_robustness_preflight.json"),
        "live_api_arbitration_regression_guard": _load_json(outputs / "reports" / "live_api_arbitration_regression_guard.json"),
        "full_generated_prompt_suite_diagnostic": _load_json(outputs / "reports" / "full_generated_prompt_suite_diagnostic.json"),
        "nl_sql_robustness_audit": _load_json(outputs / "reports" / "nl_sql_robustness_audit.json"),
        "nl_sql_paraphrase_consistency": _load_json(outputs / "reports" / "nl_sql_paraphrase_consistency.json"),
        "schema_aware_sql_failure_decomposition": _load_json(outputs / "reports" / "schema_aware_sql_failure_decomposition.json"),
        "schema_aware_sql_feedback_loop": _load_json(outputs / "reports" / "schema_aware_sql_feedback_loop.json"),
        "llm_agent_trace_decomposition": _load_json(outputs / "reports" / "llm_agent_trace_decomposition.json"),
        "controller_rewrite_policy_trial": _load_json(outputs / "reports" / "controller_rewrite_policy_trial.json"),
        "multi_llm_backend_robustness": _load_json(outputs / "reports" / "multi_llm_backend_robustness.json"),
        "live_tool_efficiency_audit": _load_json(outputs / "reports" / "live_tool_efficiency_audit.json"),
        "integrated_robustness_gate": _load_json(outputs / "reports" / "integrated_robustness_gate.json"),
        "llm_backend": _load_json(outputs / "llm_sdk_backend_check.json"),
        "llm_baseline": _load_json(outputs / "llm_baseline_eval_report.json"),
        "llm_strict": _load_json(outputs / "llm_strict_baseline_eval.json"),
        "llm_hidden": _load_json(outputs / "llm_hidden_style_diagnostic.json"),
        "llm_semantic_router": _load_json(outputs / "reports" / "llm_semantic_router_shadow_eval.json"),
        "llm_semantic_router_isolated": _load_json(outputs / "reports" / "llm_semantic_router_isolated_trial.json"),
        "llm_semantic_router_promotion": _load_json(outputs / "reports" / "llm_semantic_router_promotion_decision.json"),
        "generated_prompt_suite": _load_json(outputs / "reports" / "generated_prompt_suite_summary.json"),
        "diagnostic_prompt_suite_run": _load_json(outputs / "reports" / "diagnostic_prompt_suite_run.json"),
        "generated_prompt_suite_local_diagnostic": _load_json(outputs / "reports" / "generated_prompt_suite_local_diagnostic.json"),
        "generated_prompt_local_gap_samples": _load_json(outputs / "reports" / "generated_prompt_local_gap_samples.json"),
        "local_deterministic_improvement_candidates": _load_json(outputs / "reports" / "local_deterministic_improvement_candidates.json"),
        "superpowers_next_steps_preflight": _load_json(outputs / "reports" / "superpowers_next_steps_preflight.json"),
        "local_gap_manual_review": _load_json(outputs / "reports" / "local_gap_manual_review.json"),
        "superpowers_fix_decision": _load_json(outputs / "reports" / "superpowers_fix_decision.json"),
        "context7_docs_audit_preflight": _load_json(outputs / "reports" / "context7_docs_audit_preflight.json"),
        "context7_dependency_docs_summary": _load_json(outputs / "reports" / "context7_dependency_docs_summary.json"),
        "context7_code_alignment_audit": _load_json(outputs / "reports" / "context7_code_alignment_audit.json"),
        "context7_fix_decision": _load_json(outputs / "reports" / "context7_fix_decision.json"),
        "visualization_sync_audit": _load_json(outputs / "reports" / "visualization_sync_audit.json"),
        "full_project_dataflow": _load_json(visualizations / "full_project_dataflow.json"),
        "full_project_dataflow_svg_audit": _load_json(outputs / "reports" / "full_project_dataflow_svg_audit.json"),
        "sdk_usage_audit": _load_json(outputs / "reports" / "sdk_usage_audit.json"),
        "workshop_requirement_audit": _load_json(outputs / "reports" / "workshop_requirement_audit.json"),
        "workflow_decision_map": _load_json(outputs / "reports" / "workflow_decision_map.json"),
        "workflow_decision_audit": _load_json(outputs / "reports" / "workflow_decision_audit.json"),
        "improvement_feedback_loop_index": _load_json(outputs / "reports" / "improvement_feedback_loop_index.json"),
        "feedback_loop_semantic_router_final": _load_json(outputs / "reports" / "feedback_loop_semantic_router_final.json"),
        "decision_stage_improvement_summary": _load_json(outputs / "reports" / "decision_stage_improvement_summary.json"),
        "evidence_usage_audit": _load_json(outputs / "reports" / "evidence_usage_audit.json"),
        "evidence_aware_answer_rewrite_trial": _load_json(outputs / "reports" / "evidence_aware_answer_rewrite_trial.json"),
        "feedback_loop_answer_synthesis_final": _load_json(outputs / "reports" / "feedback_loop_answer_synthesis_final.json"),
        "sql_evidence_usage_audit": _load_json(outputs / "reports" / "sql_evidence_usage_audit.json"),
        "score_path_contribution_audit": _load_json(outputs / "reports" / "score_path_contribution_audit.json"),
        "score_focused_core_improvement_trials": _load_json(outputs / "reports" / "score_focused_core_improvement_trials.json"),
        "score_focused_core_fix_decision": _load_json(outputs / "reports" / "score_focused_core_fix_decision.json"),
        "comprehensive_failure_analysis_preflight": _load_json(outputs / "reports" / "comprehensive_failure_analysis_preflight.json"),
        "official_row_failure_table": _load_json(outputs / "reports" / "official_row_failure_table.json"),
        "generated_prompt_failure_table": _load_json(outputs / "reports" / "generated_prompt_failure_table.json"),
        "cross_dataset_failure_clusters": _load_json(outputs / "reports" / "cross_dataset_failure_clusters.json"),
        "general_deterministic_rule_candidates": _load_json(outputs / "reports" / "general_deterministic_rule_candidates.json"),
        "cross_dataset_counterfactual_answer_sketches": _load_json(outputs / "reports" / "cross_dataset_counterfactual_answer_sketches.json"),
        "general_rule_hardcoding_risk_audit": _load_json(outputs / "reports" / "general_rule_hardcoding_risk_audit.json"),
        "comprehensive_failure_fix_decision": _load_json(outputs / "reports" / "comprehensive_failure_fix_decision.json"),
        "deterministic_prompt_type_audit": _load_json(outputs / "reports" / "deterministic_prompt_type_audit.json"),
        "type_specific_deterministic_rule_candidates": _load_json(outputs / "reports" / "type_specific_deterministic_rule_candidates.json"),
        "type_specific_deterministic_rule_trials": _load_json(outputs / "reports" / "type_specific_deterministic_rule_trials.json"),
        "type_specific_rule_fix_decision": _load_json(outputs / "reports" / "type_specific_rule_fix_decision.json"),
        "sdk_tool_calling_optimization_preflight": _load_json(outputs / "reports" / "sdk_tool_calling_optimization_preflight.json"),
        "sdk_tool_call_surface_audit": _load_json(outputs / "reports" / "sdk_tool_call_surface_audit.json"),
        "sdk_tool_call_decision_analysis": _load_json(outputs / "reports" / "sdk_tool_call_decision_analysis.json"),
        "sdk_tool_call_optimization_variants": _load_json(outputs / "reports" / "sdk_tool_call_optimization_variants.json"),
        "sdk_tool_calling_optimization_trials": _load_json(outputs / "reports" / "sdk_tool_calling_optimization_trials.json"),
        "sdk_tool_calling_fix_decision": _load_json(outputs / "reports" / "sdk_tool_calling_fix_decision.json"),
        "correctness_efficiency_scorecard": _load_json(outputs / "reports" / "correctness_efficiency_scorecard.json"),
        "correctness_efficiency_fix_decision": _load_json(outputs / "reports" / "correctness_efficiency_fix_decision.json"),
        "sdk_tool_calling_promotion_preflight": _load_json(outputs / "reports" / "sdk_tool_calling_promotion_preflight.json"),
        "sdk_tool_calling_promotion_plan": _load_json(outputs / "reports" / "sdk_tool_calling_promotion_plan.json"),
        "sdk_tool_calling_efficiency_promotion_decision": _load_json(outputs / "reports" / "sdk_tool_calling_efficiency_promotion_decision.json"),
        "tool_calling_policy_optimizer": _load_json(outputs / "reports" / "tool_calling_policy_optimizer.json"),
        "tool_calling_objective_functions": _load_json(outputs / "reports" / "tool_calling_objective_functions.json"),
        "tool_calling_policy_search_results": _load_json(outputs / "reports" / "tool_calling_policy_search_results.json"),
        "tool_calling_compiled_policy_candidate": _load_json(outputs / "reports" / "tool_calling_compiled_policy_candidate.json"),
        "tool_calling_policy_promotion_decision": _load_json(outputs / "reports" / "tool_calling_policy_promotion_decision.json"),
        "core_tool_optimization_audit": _load_json(outputs / "reports" / "core_tool_optimization_audit.json"),
        "core_tool_optimization_search_space": _load_json(outputs / "reports" / "core_tool_optimization_search_space.json"),
        "core_tool_policy_optimizer": _load_json(outputs / "reports" / "core_tool_policy_optimizer.json"),
        "core_tool_policy_search_results": _load_json(outputs / "reports" / "core_tool_policy_search_results.json"),
        "execute_sql_optimization_candidates": _load_json(outputs / "reports" / "execute_sql_optimization_candidates.json"),
        "call_api_optimization_candidates": _load_json(outputs / "reports" / "call_api_optimization_candidates.json"),
        "core_tool_compiled_policy_candidate": _load_json(outputs / "reports" / "core_tool_compiled_policy_candidate.json"),
        "core_tool_policy_promotion_decision": _load_json(outputs / "reports" / "core_tool_policy_promotion_decision.json"),
        "repo_cleanup_preflight": _load_json(outputs / "reports" / "repo_cleanup_preflight.json"),
        "repo_cleanup_candidate_inventory": _load_json(outputs / "reports" / "repo_cleanup_candidate_inventory.json"),
        "repo_cleanup_deletion_plan": _load_json(outputs / "reports" / "repo_cleanup_deletion_plan.json"),
        "repo_cleanup_result": _load_json(outputs / "reports" / "repo_cleanup_result.json"),
        "dashsys_project_skill_audit": _load_json(outputs / "reports" / "dashsys_project_skill_audit.json"),
        "confidence_calibration_audit": _load_json(outputs / "reports" / "confidence_calibration_audit.json"),
        "token_efficiency_audit": _load_json(outputs / "reports" / "token_efficiency_audit.json"),
        "end_to_end_system_dataflow": _load_json(visualizations / "end_to_end_system_dataflow.json"),
        "sql_storyboard": _load_json(visualizations / "sql_prompt_storyboard_primary.json"),
        "visualization_index": _load_json(visualizations / "index.json"),
    }


def _maybe_generate_end_to_end_system_dataflow(config: Config) -> None:
    if config.project_root.resolve() != ROOT.resolve() or config.outputs_dir.resolve() != (ROOT / "outputs").resolve():
        return
    from scripts.generate_end_to_end_system_dataflow import generate_end_to_end_system_dataflow

    generate_end_to_end_system_dataflow()


def _maybe_generate_project_mermaid_visualizations(config: Config) -> None:
    from scripts.generate_project_mermaid_visualizations import generate_project_mermaid_visualizations

    generate_project_mermaid_visualizations(config)


def _maybe_generate_full_project_dataflow_svg(config: Config) -> None:
    from scripts.generate_full_project_dataflow_svg import generate_full_project_dataflow_svg

    generate_full_project_dataflow_svg(config)


def build_system_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    strict = _sql_first_metrics(sources)
    packaged = sources["winner_readiness"].get("packaged", {})
    hidden = sources["hidden_style"].get("summary", {})
    official = sources["official_token_reduction"].get("summary", {})
    best_isolated = _best_isolated_score(sources)
    return {
        "report_type": "system_summary",
        "purpose": "One-glance supervisor/submission summary of the current deterministic packaged system.",
        "preferred_strategy": packaged.get("preferred_strategy") or "SQL_FIRST_API_VERIFY",
        "packaged_strict_score": _first_number(packaged.get("strict_final_score"), strict.get("avg_final_score")),
        "best_isolated_score": best_isolated,
        "strict_correctness": _first_number(packaged.get("strict_correctness"), strict.get("avg_correctness_score")),
        "hidden_style": {
            "passed": hidden.get("passed_cases"),
            "total": hidden.get("total_cases"),
            "label": _hidden_label(hidden),
        },
        "final_submission_ready": packaged.get("final_submission_ready"),
        "official_token_reduction_enabled": official.get("promotion_kept", True),
        "repair_execution_enabled": sources["hidden_style"].get("repair_execution_enabled", False),
        "compact_context_enabled": sources["hidden_style"].get("compact_context_enabled", False),
        "runtime": _first_number(packaged.get("runtime"), strict.get("avg_runtime")),
        "tool_calls": _first_number(packaged.get("tool_calls"), strict.get("avg_tool_call_count")),
        "estimated_tokens": _first_number(packaged.get("estimated_tokens"), strict.get("avg_estimated_tokens")),
        "architecture": [
            "Deterministic-first natural-language QA agent",
            "DuckDB SQL over local parquet snapshots",
            "Adobe API execution is live-ready when credentials are present; dry-run is an honest local fallback",
            "Evidence-driven answer synthesis and trajectory logging",
        ],
        "workflow": [
            "Prompt normalization and query analysis",
            "Metadata/context selection",
            "SQL_FIRST_API_VERIFY planning",
            "Validated SQL/API execution",
            "Evidence extraction, answer synthesis, verification, and packaging",
        ],
        "final_recommendation": sources["winner_readiness"].get("final_recommendation", "ready_to_submit_with_official_token_reduction"),
        "live_adobe_api_readiness": _live_api_readiness_status(sources),
        "post_live_robustness": _post_live_robustness_status(sources),
        "llm_semantic_routing_helper": _semantic_router_status(sources),
        "decision_stage_methodology": _decision_stage_status(sources),
        "evidence_aware_answer_synthesis": _evidence_answer_status(sources),
        "score_focused_core_path": _score_path_status(sources),
        "comprehensive_failure_analysis": _comprehensive_failure_status(sources),
        "type_specific_deterministic_rules": _type_specific_rule_status(sources),
        "sdk_tool_calling_optimization": _sdk_tool_calling_optimization_status(sources),
        "correctness_efficiency_evaluation": _correctness_efficiency_status(sources),
        "sdk_tool_calling_efficiency_promotion": _sdk_tool_calling_efficiency_promotion_status(sources),
        "tool_calling_policy_optimizer": _tool_calling_policy_optimizer_status(sources),
        "core_tool_policy_optimizer": _core_tool_policy_optimizer_status(sources),
        "repo_cleanup": _repo_cleanup_status(sources),
        "dashsys_project_skill": _dashsys_project_skill_status(sources),
        "context7_documentation_grounded_audit": _context7_audit_status(sources),
        "source_reports": [
            "outputs/eval_results_strict.json",
            "outputs/winner_readiness_report.json",
            "outputs/hidden_style_eval.json",
            "outputs/official_token_reduction_promotion_report.json",
            "outputs/reports/post_permission_live_api_verification.md",
            "outputs/reports/adobe_access_waiting_status.md",
            "outputs/reports/post_live_robustness_preflight.md",
            "outputs/reports/live_api_arbitration_regression_guard.md",
            "outputs/reports/full_generated_prompt_suite_diagnostic.md",
            "outputs/reports/nl_sql_robustness_audit.md",
            "outputs/reports/nl_sql_paraphrase_consistency.md",
            "outputs/reports/schema_aware_sql_failure_decomposition.md",
            "outputs/reports/schema_aware_sql_feedback_loop.md",
            "outputs/reports/llm_agent_trace_decomposition.md",
            "outputs/reports/controller_rewrite_policy_trial.md",
            "outputs/reports/multi_llm_backend_robustness.md",
            "outputs/reports/live_tool_efficiency_audit.md",
            "outputs/reports/integrated_robustness_gate.md",
            "outputs/reports/context7_code_alignment_audit.md",
            "outputs/reports/context7_fix_decision.md",
            "outputs/reports/score_path_contribution_audit.md",
            "outputs/reports/score_focused_core_improvement_trials.md",
            "outputs/reports/score_focused_core_fix_decision.md",
            "outputs/reports/official_row_failure_table.md",
            "outputs/reports/generated_prompt_failure_table.md",
            "outputs/reports/cross_dataset_failure_clusters.md",
            "outputs/reports/general_deterministic_rule_candidates.md",
            "outputs/reports/general_rule_hardcoding_risk_audit.md",
            "outputs/reports/comprehensive_failure_fix_decision.md",
            "outputs/reports/deterministic_prompt_type_audit.md",
            "outputs/reports/type_specific_deterministic_rule_candidates.md",
            "outputs/reports/type_specific_deterministic_rule_trials.md",
            "outputs/reports/type_specific_rule_fix_decision.md",
            "outputs/reports/sdk_tool_calling_optimization_preflight.md",
            "outputs/reports/sdk_tool_call_surface_audit.md",
            "outputs/reports/sdk_tool_call_decision_analysis.md",
            "outputs/reports/sdk_tool_call_optimization_variants.md",
            "outputs/reports/sdk_tool_calling_optimization_trials.md",
            "outputs/reports/sdk_tool_calling_fix_decision.md",
            "outputs/reports/correctness_efficiency_scorecard.md",
            "outputs/reports/correctness_efficiency_fix_decision.md",
            "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md",
            "outputs/reports/tool_calling_policy_optimizer.md",
            "outputs/reports/tool_calling_policy_search_results.md",
            "outputs/reports/tool_calling_compiled_policy_candidate.md",
            "outputs/reports/tool_calling_policy_promotion_decision.md",
            "outputs/reports/core_tool_optimization_audit.md",
            "outputs/reports/core_tool_policy_optimizer.md",
            "outputs/reports/core_tool_compiled_policy_candidate.md",
            "outputs/reports/core_tool_policy_promotion_decision.md",
            "outputs/reports/repo_cleanup_result.md",
            "outputs/reports/dashsys_project_skill_audit.md",
        ],
    }


def build_llm_baseline_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    baseline = sources["llm_baseline"]
    strict = sources["llm_strict"]
    per_strategy = baseline.get("per_strategy") or strict.get("per_strategy") or []
    best = _best_llm_strategy(per_strategy)
    deterministic = baseline.get("deterministic_sql_first_api_verify", {})
    return {
        "report_type": "llm_baseline_summary",
        "framework": baseline.get("framework") or strict.get("framework") or "generic_sdk_llm_baseline",
        "framework_note": "The LLM baseline framework is generic; Qwen is only the current configured backend/model metadata.",
        "current_backend_model": baseline.get("backend_name") or strict.get("backend_name") or sources["llm_backend"].get("backend_name"),
        "provider_type": baseline.get("provider_type") or strict.get("provider_type") or sources["llm_backend"].get("provider_type"),
        "backend_type": baseline.get("backend_type") or strict.get("backend_type") or sources["llm_backend"].get("backend_type"),
        "anthropic_sdk_support": "available_in_client; configure LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY",
        "tool_calling_supported": baseline.get("tool_calling_supported", sources["llm_backend"].get("tool_calling_supported")),
        "smoke_test_passed": baseline.get("smoke_test_passed", sources["llm_backend"].get("ok")),
        "strict_scoring_status": baseline.get("strict_scoring_status", strict.get("summary", {}).get("strict_scoring_status")),
        "best_llm_baseline": best,
        "best_llm_baseline_score": best.get("strict_score") or best.get("strict_final_score"),
        "sql_first_api_verify_score": deterministic.get("avg_final_score") or _sql_first_metrics(sources).get("avg_final_score"),
        "comparison_against_deterministic": strict.get("comparison_against_deterministic") or baseline.get("comparison_against_deterministic"),
        "recommendation": baseline.get("recommendation") or strict.get("summary", {}).get("recommendation") or "keep_shadow_only",
        "reason": "Deterministic SQL_FIRST_API_VERIFY remains higher under strict scoring.",
        "llm_semantic_routing_helper": _semantic_router_status(sources),
        "decision_stage_methodology": _decision_stage_status(sources),
        "evidence_aware_answer_synthesis": _evidence_answer_status(sources),
        "score_focused_core_path": _score_path_status(sources),
        "comprehensive_failure_analysis": _comprehensive_failure_status(sources),
        "type_specific_deterministic_rules": _type_specific_rule_status(sources),
        "sdk_tool_calling_optimization": _sdk_tool_calling_optimization_status(sources),
        "correctness_efficiency_evaluation": _correctness_efficiency_status(sources),
        "sdk_tool_calling_efficiency_promotion": _sdk_tool_calling_efficiency_promotion_status(sources),
        "tool_calling_policy_optimizer": _tool_calling_policy_optimizer_status(sources),
        "core_tool_policy_optimizer": _core_tool_policy_optimizer_status(sources),
        "source_reports": [
            "outputs/llm_sdk_backend_check.json",
            "outputs/llm_baseline_eval_report.json",
            "outputs/llm_strict_baseline_eval.json",
            "outputs/llm_hidden_style_diagnostic.json",
            "outputs/reports/sdk_tool_call_surface_audit.md",
            "outputs/reports/sdk_tool_calling_optimization_trials.md",
            "outputs/reports/sdk_tool_calling_fix_decision.md",
            "outputs/reports/correctness_efficiency_scorecard.md",
            "outputs/reports/correctness_efficiency_fix_decision.md",
            "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md",
            "outputs/reports/tool_calling_policy_optimizer.md",
            "outputs/reports/tool_calling_policy_search_results.md",
            "outputs/reports/tool_calling_compiled_policy_candidate.md",
            "outputs/reports/tool_calling_policy_promotion_decision.md",
            "outputs/reports/core_tool_optimization_audit.md",
            "outputs/reports/core_tool_policy_optimizer.md",
            "outputs/reports/core_tool_compiled_policy_candidate.md",
            "outputs/reports/core_tool_policy_promotion_decision.md",
        ],
    }


def build_accuracy_and_bottleneck_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    autonomous = sources["autonomous_score_push"].get("summary", {})
    trial = sources["autonomous_trial"].get("summary", {})
    best_isolated = _best_isolated_score(sources)
    return {
        "report_type": "accuracy_and_bottleneck_summary",
        "starting_score": autonomous.get("starting_score", 0.6491),
        "best_isolated_score": best_isolated,
        "target_0_70_reached": bool(autonomous.get("target_0_70_reached", False) or trial.get("target_0_70_reached", False)),
        "target_0_75_reached": bool(autonomous.get("target_0_75_reached", False) or trial.get("target_0_75_reached", False)),
        "answer_quality_bottleneck": True,
        "dry_run_api_limitation": True,
        "live_adobe_api_readiness": _live_api_readiness_status(sources),
        "post_live_robustness": _post_live_robustness_status(sources),
        "answer_shape_v2_status": _status_from_report(sources["answer_shape_v2"], "shadow_only"),
        "supportable_rewrite_status": _status_from_report(sources["supportable_rewrite"], "safe_for_autonomous_packaged_trial"),
        "llm_answer_rewrite_status": _status_from_report(sources["llm_answer_rewrite"], "keep_shadow_only"),
        "endpoint_tiebreak_status": _status_from_report(sources["endpoint_tiebreak"], "keep_shadow_only"),
        "endpoint_schema_canary_status": _status_from_report(sources["endpoint_schema_canary"], "keep_shadow_only"),
        "ast_canary_status": _status_from_report(sources["ast_canary"], "keep_shadow_only"),
        "why_shadow_only": [
            "The 0.70 and 0.75 targets were not reached safely.",
            "Live Adobe API readiness is now the primary API-path infrastructure target; dry-run wording remains fallback polish.",
            "Endpoint/schema and AST changes are report-only or shadow-only unless strict gates improve.",
            "The LLM semantic routing helper is default-off and remains shadow-only unless a later strict/safety gate promotes it.",
        ],
        "llm_semantic_routing_helper": _semantic_router_status(sources),
        "decision_stage_methodology": _decision_stage_status(sources),
        "evidence_aware_answer_synthesis": _evidence_answer_status(sources),
        "score_focused_core_path": _score_path_status(sources),
        "comprehensive_failure_analysis": _comprehensive_failure_status(sources),
        "type_specific_deterministic_rules": _type_specific_rule_status(sources),
        "sdk_tool_calling_optimization": _sdk_tool_calling_optimization_status(sources),
        "correctness_efficiency_evaluation": _correctness_efficiency_status(sources),
        "sdk_tool_calling_efficiency_promotion": _sdk_tool_calling_efficiency_promotion_status(sources),
        "tool_calling_policy_optimizer": _tool_calling_policy_optimizer_status(sources),
        "core_tool_policy_optimizer": _core_tool_policy_optimizer_status(sources),
        "source_reports": [
            "outputs/autonomous_score_push_report.json",
            "outputs/autonomous_packaged_trial.json",
            "outputs/score075_blocker_analysis.json",
            "outputs/supportable_answer_rewrite_eval.json",
            "outputs/endpoint_family_tiebreak_v2_shadow.json",
            "outputs/ast_guided_sql_candidate_canary.json",
            "outputs/reports/live_adobe_api_readiness_audit.json",
            "outputs/reports/post_live_robustness_preflight.md",
            "outputs/reports/live_api_arbitration_regression_guard.md",
            "outputs/reports/full_generated_prompt_suite_diagnostic.md",
            "outputs/reports/nl_sql_robustness_audit.md",
            "outputs/reports/nl_sql_paraphrase_consistency.md",
            "outputs/reports/schema_aware_sql_failure_decomposition.md",
            "outputs/reports/schema_aware_sql_feedback_loop.md",
            "outputs/reports/llm_agent_trace_decomposition.md",
            "outputs/reports/controller_rewrite_policy_trial.md",
            "outputs/reports/multi_llm_backend_robustness.md",
            "outputs/reports/live_tool_efficiency_audit.md",
            "outputs/reports/integrated_robustness_gate.md",
            "outputs/reports/generated_prompt_suite_local_diagnostic.md",
            "outputs/reports/generated_prompt_local_gap_samples.md",
            "outputs/reports/local_deterministic_improvement_candidates.md",
            "outputs/reports/superpowers_next_steps_preflight.md",
            "outputs/reports/local_gap_manual_review.md",
            "outputs/reports/superpowers_fix_decision.md",
            "outputs/reports/context7_dependency_docs_summary.md",
            "outputs/reports/context7_code_alignment_audit.md",
            "outputs/reports/context7_fix_decision.md",
            "outputs/reports/score_path_contribution_audit.md",
            "outputs/reports/score_focused_core_improvement_trials.md",
            "outputs/reports/score_focused_core_fix_decision.md",
            "outputs/reports/official_row_failure_table.md",
            "outputs/reports/generated_prompt_failure_table.md",
            "outputs/reports/cross_dataset_failure_clusters.md",
            "outputs/reports/general_deterministic_rule_candidates.md",
            "outputs/reports/general_rule_hardcoding_risk_audit.md",
            "outputs/reports/comprehensive_failure_fix_decision.md",
            "outputs/reports/deterministic_prompt_type_audit.md",
            "outputs/reports/type_specific_deterministic_rule_candidates.md",
            "outputs/reports/type_specific_deterministic_rule_trials.md",
            "outputs/reports/type_specific_rule_fix_decision.md",
            "outputs/reports/sdk_tool_calling_optimization_trials.md",
            "outputs/reports/sdk_tool_calling_fix_decision.md",
            "outputs/reports/correctness_efficiency_scorecard.md",
            "outputs/reports/correctness_efficiency_fix_decision.md",
            "outputs/reports/sdk_tool_calling_promotion_preflight.md",
            "outputs/reports/sdk_tool_calling_promotion_plan.md",
            "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md",
            "outputs/reports/tool_calling_policy_optimizer.md",
            "outputs/reports/tool_calling_policy_search_results.md",
            "outputs/reports/tool_calling_compiled_policy_candidate.md",
            "outputs/reports/tool_calling_policy_promotion_decision.md",
            "outputs/reports/core_tool_optimization_audit.md",
            "outputs/reports/core_tool_policy_optimizer.md",
            "outputs/reports/core_tool_compiled_policy_candidate.md",
            "outputs/reports/core_tool_policy_promotion_decision.md",
        ],
    }


def build_visualization_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    story = sources["sql_storyboard"]
    return {
        "report_type": "visualization_summary",
        "primary_example": story.get("query_id", "example_011"),
        "raw_prompt": story.get("raw_prompt", "How many schemas do I have?"),
        "prompt_to_sql_mapping": {
            "schemas": story.get("selected_table", "dim_blueprint"),
            "how_many": story.get("aggregation", "COUNT DISTINCT"),
            "identifier_column": story.get("selected_column", "BLUEPRINTID"),
            "result": story.get("sql_result_summary", "blueprint_count = 74"),
        },
        "main_storyboard": "outputs/visualizations/sql_prompt_storyboard_primary.md",
        "end_to_end_system_dataflow": "outputs/visualizations/end_to_end_system_dataflow.html",
        "single_svg_project_overview": "outputs/visualizations/full_project_dataflow.svg",
        "supervisor_visualizations": [
            "outputs/visualizations/executive_dashboard.md",
            "outputs/visualizations/end_to_end_system_dataflow.html",
            "outputs/visualizations/full_project_dataflow.svg",
            "outputs/visualizations/full_project_dataflow.md",
            "outputs/visualizations/project_architecture_c4.md",
            "outputs/visualizations/end_to_end_pipeline_mermaid.md",
            "outputs/visualizations/live_adobe_api_status_mermaid.md",
            "outputs/visualizations/report_generation_map.md",
            "outputs/visualizations/sql_prompt_storyboard_primary.md",
            "outputs/visualizations/system_status_dashboard.md",
            "outputs/visualizations/technique_visual_cards.md",
            "outputs/visualizations/end_to_end_system_dataflow.md",
            "outputs/visualizations/score_bottleneck_dashboard.md",
        ],
        "secondary_reference": "example_031 remains a secondary API/dry-run bottleneck reference only.",
        "source_reports": [
            "outputs/visualizations/sql_prompt_storyboard_primary.json",
            "outputs/visualizations/end_to_end_system_dataflow.json",
            "outputs/visualizations/full_project_dataflow.json",
            "outputs/reports/full_project_dataflow_svg_audit.json",
            "outputs/visualizations/index.json",
            "outputs/reports/visualization_sync_audit.json",
        ],
    }


def build_report_index(
    config: Config,
    system: dict[str, Any],
    llm: dict[str, Any],
    accuracy: dict[str, Any],
    visualization: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_type": "report_index",
        "message": "Start here. Most older generated reports were consolidated or removed.",
        "canonical_reports": [
            "outputs/reports/system_summary.md",
            "outputs/reports/llm_baseline_summary.md",
            "outputs/reports/accuracy_and_bottleneck_summary.md",
            "outputs/reports/visualization_summary.md",
            "outputs/reports/core_tool_optimization_audit.md",
            "outputs/reports/core_tool_policy_optimizer.md",
            "outputs/reports/core_tool_compiled_policy_candidate.md",
            "outputs/reports/core_tool_correctness_audit.md",
            "outputs/reports/core_tool_correctness_trials.md",
            "outputs/reports/core_tool_correctness_fix_decision.md",
            "outputs/reports/integrated_robustness_gate.md",
            "outputs/reports/overnight_autonomous_improvement_report.md",
            "outputs/reports/repo_cleanup_result.md",
            "outputs/reports/report_index.md",
        ],
        "key_source_of_truth_reports": [
            "outputs/eval_results_strict.json",
            "outputs/winner_readiness_report.md",
            "outputs/final_research_inspired_improvement_report.md",
            "outputs/hidden_style_eval.md",
            "outputs/llm_strict_baseline_eval.md",
        ],
        "key_visualizations": visualization["supervisor_visualizations"],
        "diagnostic_prompt_coverage": [
            {
                "path": "outputs/reports/generated_prompt_suite_summary.md",
                "label": "Diagnostic prompt coverage only; not official strict score.",
            },
            {
                "path": "outputs/reports/diagnostic_prompt_suite_run.md",
                "label": "Diagnostic prompt runtime coverage only; not official strict score.",
            },
            {
                "path": "outputs/reports/generated_prompt_suite_local_diagnostic.md",
                "label": "Local dry-run 250-prompt diagnostic only; no live API calls or official score claim.",
            },
            {
                "path": "outputs/reports/generated_prompt_local_gap_samples.md",
                "label": "Representative local diagnostic gap samples; advisory-only and not promotion evidence.",
            },
            {
                "path": "outputs/reports/local_deterministic_improvement_candidates.md",
                "label": "Evidence-gated deterministic improvement candidates; no automatic runtime change.",
            },
            {
                "path": "outputs/reports/superpowers_next_steps_preflight.md",
                "label": "Superpowers-style protected-artifact preflight before any local deterministic improvement.",
            },
            {
                "path": "outputs/reports/local_gap_manual_review.md",
                "label": "Manual review of high-value local diagnostic gaps; generated labels are advisory only.",
            },
            {
                "path": "outputs/reports/superpowers_fix_decision.md",
                "label": "Evidence-gated fix decision; no runtime change unless exactly one safe candidate passes.",
            },
            {
                "path": "outputs/reports/full_generated_prompt_suite_diagnostic.md",
                "label": "Full 250-prompt generated suite diagnostic after live API stabilization; diagnostic-only and not official strict score.",
            },
            {
                "path": "outputs/reports/generated_prompt_coverage_gap_analysis.md",
                "label": "Generated prompt coverage gaps; diagnostic-only and not promotion evidence.",
            },
        ],
        "post_live_robustness": {
            "preflight_path": "outputs/reports/post_live_robustness_preflight.md",
            "arbitration_guard_path": "outputs/reports/live_api_arbitration_regression_guard.md",
            "full_generated_suite_path": "outputs/reports/full_generated_prompt_suite_diagnostic.md",
            "nl_sql_robustness_path": "outputs/reports/nl_sql_robustness_audit.md",
            "paraphrase_consistency_path": "outputs/reports/nl_sql_paraphrase_consistency.md",
            "schema_aware_failure_decomposition_path": "outputs/reports/schema_aware_sql_failure_decomposition.md",
            "schema_aware_feedback_loop_path": "outputs/reports/schema_aware_sql_feedback_loop.md",
            "llm_trace_decomposition_path": "outputs/reports/llm_agent_trace_decomposition.md",
            "controller_rewrite_trial_path": "outputs/reports/controller_rewrite_policy_trial.md",
            "multi_llm_robustness_path": "outputs/reports/multi_llm_backend_robustness.md",
            "live_tool_efficiency_path": "outputs/reports/live_tool_efficiency_audit.md",
            "integrated_gate_path": "outputs/reports/integrated_robustness_gate.md",
            **_post_live_robustness_status(
                {
                    "eval_results_strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
                    "post_live_robustness_preflight": _load_json(config.outputs_dir / "reports" / "post_live_robustness_preflight.json"),
                    "live_api_arbitration_regression_guard": _load_json(config.outputs_dir / "reports" / "live_api_arbitration_regression_guard.json"),
                    "full_generated_prompt_suite_diagnostic": _load_json(config.outputs_dir / "reports" / "full_generated_prompt_suite_diagnostic.json"),
                    "nl_sql_robustness_audit": _load_json(config.outputs_dir / "reports" / "nl_sql_robustness_audit.json"),
                    "nl_sql_paraphrase_consistency": _load_json(config.outputs_dir / "reports" / "nl_sql_paraphrase_consistency.json"),
                    "schema_aware_sql_feedback_loop": _load_json(config.outputs_dir / "reports" / "schema_aware_sql_feedback_loop.json"),
                    "llm_agent_trace_decomposition": _load_json(config.outputs_dir / "reports" / "llm_agent_trace_decomposition.json"),
                    "controller_rewrite_policy_trial": _load_json(config.outputs_dir / "reports" / "controller_rewrite_policy_trial.json"),
                    "multi_llm_backend_robustness": _load_json(config.outputs_dir / "reports" / "multi_llm_backend_robustness.json"),
                    "live_tool_efficiency_audit": _load_json(config.outputs_dir / "reports" / "live_tool_efficiency_audit.json"),
                    "integrated_robustness_gate": _load_json(config.outputs_dir / "reports" / "integrated_robustness_gate.json"),
                }
            ),
        },
        "llm_controller_diagnostics": {
            "failure_decomposition_path": "outputs/reports/llm_controller_failure_decomposition.md",
            "rewrite_ablation_path": "outputs/reports/controller_rewrite_ablation.md",
            "automatic_promotion": False,
            "controller_status": "shadow_only",
            "recommendation": _load_json(config.outputs_dir / "reports" / "controller_rewrite_ablation.json")
            .get("summary", {})
            .get("recommendation", "unavailable"),
        },
        "sdk_usage_audit": {
            "path": "outputs/reports/sdk_usage_audit.md",
            "runtime_llm_direct_http_hits": _load_json(config.outputs_dir / "reports" / "sdk_usage_audit.json")
            .get("summary", {})
            .get("runtime_llm_direct_http_hits", "unavailable"),
        },
        "sdk_tool_calling_optimization": {
            "preflight_path": "outputs/reports/sdk_tool_calling_optimization_preflight.md",
            "surface_audit_path": "outputs/reports/sdk_tool_call_surface_audit.md",
            "decision_analysis_path": "outputs/reports/sdk_tool_call_decision_analysis.md",
            "variants_path": "outputs/reports/sdk_tool_call_optimization_variants.md",
            "trials_path": "outputs/reports/sdk_tool_calling_optimization_trials.md",
            "fix_decision_path": "outputs/reports/sdk_tool_calling_fix_decision.md",
            **_sdk_tool_calling_optimization_status(
                {
                    "sdk_tool_calling_optimization_preflight": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_optimization_preflight.json"),
                    "sdk_tool_call_surface_audit": _load_json(config.outputs_dir / "reports" / "sdk_tool_call_surface_audit.json"),
                    "sdk_tool_call_decision_analysis": _load_json(config.outputs_dir / "reports" / "sdk_tool_call_decision_analysis.json"),
                    "sdk_tool_call_optimization_variants": _load_json(config.outputs_dir / "reports" / "sdk_tool_call_optimization_variants.json"),
                    "sdk_tool_calling_optimization_trials": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_optimization_trials.json"),
                    "sdk_tool_calling_fix_decision": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_fix_decision.json"),
                }
            ),
        },
        "correctness_efficiency_evaluation": {
            "scorecard_path": "outputs/reports/correctness_efficiency_scorecard.md",
            "fix_decision_path": "outputs/reports/correctness_efficiency_fix_decision.md",
            **_correctness_efficiency_status(
                {
                    "correctness_efficiency_scorecard": _load_json(config.outputs_dir / "reports" / "correctness_efficiency_scorecard.json"),
                    "correctness_efficiency_fix_decision": _load_json(config.outputs_dir / "reports" / "correctness_efficiency_fix_decision.json"),
                }
            ),
        },
        "sdk_tool_calling_efficiency_promotion": {
            "preflight_path": "outputs/reports/sdk_tool_calling_promotion_preflight.md",
            "plan_path": "outputs/reports/sdk_tool_calling_promotion_plan.md",
            "decision_path": "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md",
            **_sdk_tool_calling_efficiency_promotion_status(
                {
                    "sdk_tool_calling_promotion_preflight": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_promotion_preflight.json"),
                    "sdk_tool_calling_promotion_plan": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_promotion_plan.json"),
                    "sdk_tool_calling_efficiency_promotion_decision": _load_json(config.outputs_dir / "reports" / "sdk_tool_calling_efficiency_promotion_decision.json"),
                }
            ),
        },
        "core_tool_policy_optimizer": {
            "audit_path": "outputs/reports/core_tool_optimization_audit.md",
            "search_space_path": "outputs/reports/core_tool_optimization_search_space.md",
            "optimizer_path": "outputs/reports/core_tool_policy_optimizer.md",
            "search_results_path": "outputs/reports/core_tool_policy_search_results.md",
            "execute_sql_candidates_path": "outputs/reports/execute_sql_optimization_candidates.md",
            "call_api_candidates_path": "outputs/reports/call_api_optimization_candidates.md",
            "compiled_candidate_path": "outputs/reports/core_tool_compiled_policy_candidate.md",
            "promotion_decision_path": "outputs/reports/core_tool_policy_promotion_decision.md",
            **_core_tool_policy_optimizer_status(
                {
                    "core_tool_optimization_audit": _load_json(config.outputs_dir / "reports" / "core_tool_optimization_audit.json"),
                    "core_tool_optimization_search_space": _load_json(config.outputs_dir / "reports" / "core_tool_optimization_search_space.json"),
                    "core_tool_policy_optimizer": _load_json(config.outputs_dir / "reports" / "core_tool_policy_optimizer.json"),
                    "core_tool_policy_search_results": _load_json(config.outputs_dir / "reports" / "core_tool_policy_search_results.json"),
                    "execute_sql_optimization_candidates": _load_json(config.outputs_dir / "reports" / "execute_sql_optimization_candidates.json"),
                    "call_api_optimization_candidates": _load_json(config.outputs_dir / "reports" / "call_api_optimization_candidates.json"),
                    "core_tool_compiled_policy_candidate": _load_json(config.outputs_dir / "reports" / "core_tool_compiled_policy_candidate.json"),
                    "core_tool_policy_promotion_decision": _load_json(config.outputs_dir / "reports" / "core_tool_policy_promotion_decision.json"),
                }
            ),
        },
        "dashsys_project_skill": {
            "skill_path": "skills/dashsys_project_skill/SKILL.md",
            "audit_path": "outputs/reports/dashsys_project_skill_audit.md",
            **_dashsys_project_skill_status(
                {
                    "dashsys_project_skill_audit": _load_json(config.outputs_dir / "reports" / "dashsys_project_skill_audit.json"),
                }
            ),
        },
        "context7_documentation_grounded_audit": {
            "preflight_path": "outputs/reports/context7_docs_audit_preflight.md",
            "docs_summary_path": "outputs/reports/context7_dependency_docs_summary.md",
            "code_alignment_path": "outputs/reports/context7_code_alignment_audit.md",
            "fix_decision_path": "outputs/reports/context7_fix_decision.md",
            **_context7_audit_status(
                {
                    "context7_docs_audit_preflight": _load_json(config.outputs_dir / "reports" / "context7_docs_audit_preflight.json"),
                    "context7_dependency_docs_summary": _load_json(config.outputs_dir / "reports" / "context7_dependency_docs_summary.json"),
                    "context7_code_alignment_audit": _load_json(config.outputs_dir / "reports" / "context7_code_alignment_audit.json"),
                    "context7_fix_decision": _load_json(config.outputs_dir / "reports" / "context7_fix_decision.json"),
                }
            ),
        },
        "score_focused_core_path": {
            "contribution_audit_path": "outputs/reports/score_path_contribution_audit.md",
            "trials_path": "outputs/reports/score_focused_core_improvement_trials.md",
            "fix_decision_path": "outputs/reports/score_focused_core_fix_decision.md",
            **_score_path_status(
                {
                    "score_path_contribution_audit": _load_json(config.outputs_dir / "reports" / "score_path_contribution_audit.json"),
                    "score_focused_core_improvement_trials": _load_json(config.outputs_dir / "reports" / "score_focused_core_improvement_trials.json"),
                    "score_focused_core_fix_decision": _load_json(config.outputs_dir / "reports" / "score_focused_core_fix_decision.json"),
                }
            ),
        },
        "comprehensive_failure_analysis": {
            "preflight_path": "outputs/reports/comprehensive_failure_analysis_preflight.md",
            "official_row_failure_table_path": "outputs/reports/official_row_failure_table.md",
            "generated_prompt_failure_table_path": "outputs/reports/generated_prompt_failure_table.md",
            "cross_dataset_clusters_path": "outputs/reports/cross_dataset_failure_clusters.md",
            "rule_candidates_path": "outputs/reports/general_deterministic_rule_candidates.md",
            "counterfactual_sketches_path": "outputs/reports/cross_dataset_counterfactual_answer_sketches.md",
            "hardcoding_risk_audit_path": "outputs/reports/general_rule_hardcoding_risk_audit.md",
            "fix_decision_path": "outputs/reports/comprehensive_failure_fix_decision.md",
            **_comprehensive_failure_status(
                {
                    "comprehensive_failure_analysis_preflight": _load_json(config.outputs_dir / "reports" / "comprehensive_failure_analysis_preflight.json"),
                    "official_row_failure_table": _load_json(config.outputs_dir / "reports" / "official_row_failure_table.json"),
                    "generated_prompt_failure_table": _load_json(config.outputs_dir / "reports" / "generated_prompt_failure_table.json"),
                    "cross_dataset_failure_clusters": _load_json(config.outputs_dir / "reports" / "cross_dataset_failure_clusters.json"),
                    "general_deterministic_rule_candidates": _load_json(config.outputs_dir / "reports" / "general_deterministic_rule_candidates.json"),
                    "general_rule_hardcoding_risk_audit": _load_json(config.outputs_dir / "reports" / "general_rule_hardcoding_risk_audit.json"),
                    "comprehensive_failure_fix_decision": _load_json(config.outputs_dir / "reports" / "comprehensive_failure_fix_decision.json"),
                }
            ),
        },
        "type_specific_deterministic_rules": {
            "prompt_type_audit_path": "outputs/reports/deterministic_prompt_type_audit.md",
            "rule_candidates_path": "outputs/reports/type_specific_deterministic_rule_candidates.md",
            "rule_trials_path": "outputs/reports/type_specific_deterministic_rule_trials.md",
            "fix_decision_path": "outputs/reports/type_specific_rule_fix_decision.md",
            **_type_specific_rule_status(
                {
                    "deterministic_prompt_type_audit": _load_json(config.outputs_dir / "reports" / "deterministic_prompt_type_audit.json"),
                    "type_specific_deterministic_rule_candidates": _load_json(config.outputs_dir / "reports" / "type_specific_deterministic_rule_candidates.json"),
                    "type_specific_deterministic_rule_trials": _load_json(config.outputs_dir / "reports" / "type_specific_deterministic_rule_trials.json"),
                    "type_specific_rule_fix_decision": _load_json(config.outputs_dir / "reports" / "type_specific_rule_fix_decision.json"),
                }
            ),
        },
        "live_adobe_api_readiness": {
            "audit_path": "outputs/reports/live_adobe_api_readiness_audit.md",
            "api_required_readiness_matrix_path": "outputs/reports/api_required_readiness_matrix.md",
            "smoke_path": "outputs/reports/live_api_readiness_smoke.md",
            "endpoint_path_diagnosis_path": "outputs/reports/live_api_endpoint_path_diagnosis.md",
            "external_blockers_path": "outputs/reports/live_api_external_blockers.md",
            "followup_commands_path": "outputs/reports/live_api_endpoint_followup_commands.md",
            "full_run_blocker_path": "outputs/reports/live_api_full_run_blocker.md",
            "post_permission_verification_path": "outputs/reports/post_permission_live_api_verification.md",
            "adobe_access_waiting_status_path": "outputs/reports/adobe_access_waiting_status.md",
            "pipeline_trial_path": "outputs/reports/live_api_evidence_pipeline_trial.md",
            "mock_pipeline_trial_path": "outputs/reports/mock_live_api_evidence_pipeline_trial.md",
            "safe_get_endpoint_matrix_path": "outputs/reports/live_api_safe_get_endpoint_matrix.md",
            "remaining_endpoint_resolution_path": "outputs/reports/live_api_remaining_endpoint_resolution_summary.md",
            "guarded_live_e2e_trial_path": "outputs/reports/guarded_dash_agent_live_e2e_trial.md",
            "post_exact_go_no_go_path": "outputs/reports/live_api_post_exact_reproduction_go_no_go.md",
            **_live_api_readiness_status(
                {
                    "live_adobe_api_readiness": _load_json(config.outputs_dir / "reports" / "live_adobe_api_readiness_audit.json"),
                    "api_required_readiness_matrix": _load_json(config.outputs_dir / "reports" / "api_required_readiness_matrix.json"),
                    "live_api_smoke": _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json"),
                    "live_api_endpoint_path_diagnosis": _load_json(config.outputs_dir / "reports" / "live_api_endpoint_path_diagnosis.json"),
                    "live_api_external_blockers": _load_json(config.outputs_dir / "reports" / "live_api_external_blockers.json"),
                    "live_api_endpoint_followup_commands": _load_json(config.outputs_dir / "reports" / "live_api_endpoint_followup_commands.json"),
                    "live_api_full_run_blocker": _load_json(config.outputs_dir / "reports" / "live_api_full_run_blocker.json"),
                    "post_permission_live_api_verification": _load_json(config.outputs_dir / "reports" / "post_permission_live_api_verification.json"),
                    "adobe_access_waiting_status": _load_json(config.outputs_dir / "reports" / "adobe_access_waiting_status.json"),
                    "live_api_safe_get_endpoint_matrix": _load_json(config.outputs_dir / "reports" / "live_api_safe_get_endpoint_matrix.json"),
                    "live_api_remaining_endpoint_resolution": _load_json(config.outputs_dir / "reports" / "live_api_remaining_endpoint_resolution_summary.json"),
                    "guarded_dash_agent_live_e2e_trial": _load_json(config.outputs_dir / "reports" / "guarded_dash_agent_live_e2e_trial.json"),
                    "live_api_post_exact_go_no_go": _load_json(config.outputs_dir / "reports" / "live_api_post_exact_reproduction_go_no_go.json"),
                    "live_api_pipeline_trial": _load_json(config.outputs_dir / "reports" / "live_api_evidence_pipeline_trial.json"),
                    "mock_live_api_pipeline_trial": _load_json(config.outputs_dir / "reports" / "mock_live_api_evidence_pipeline_trial.json"),
                }
            ),
        },
        "llm_semantic_routing_helper": {
            "path": "outputs/reports/llm_semantic_router_shadow_eval.md",
            "isolated_trial_path": "outputs/reports/llm_semantic_router_isolated_trial.md",
            "promotion_decision_path": "outputs/reports/llm_semantic_router_promotion_decision.md",
            **_semantic_router_status(
                {
                    "llm_semantic_router": _load_json(config.outputs_dir / "reports" / "llm_semantic_router_shadow_eval.json"),
                    "llm_semantic_router_isolated": _load_json(config.outputs_dir / "reports" / "llm_semantic_router_isolated_trial.json"),
                    "llm_semantic_router_promotion": _load_json(config.outputs_dir / "reports" / "llm_semantic_router_promotion_decision.json"),
                }
            ),
        },
        "decision_stage_audit_and_feedback_loops": {
            "workflow_decision_map": "outputs/reports/workflow_decision_map.md",
            "workflow_decision_audit": "outputs/reports/workflow_decision_audit.md",
            "feedback_loop_index": "outputs/reports/improvement_feedback_loop_index.md",
            "semantic_router_feedback_loop_final": "outputs/reports/feedback_loop_semantic_router_final.md",
            "decision_stage_improvement_summary": "outputs/reports/decision_stage_improvement_summary.md",
            **_decision_stage_status(
                {
                    "workflow_decision_map": _load_json(config.outputs_dir / "reports" / "workflow_decision_map.json"),
                    "workflow_decision_audit": _load_json(config.outputs_dir / "reports" / "workflow_decision_audit.json"),
                    "improvement_feedback_loop_index": _load_json(config.outputs_dir / "reports" / "improvement_feedback_loop_index.json"),
                    "feedback_loop_semantic_router_final": _load_json(config.outputs_dir / "reports" / "feedback_loop_semantic_router_final.json"),
                    "decision_stage_improvement_summary": _load_json(config.outputs_dir / "reports" / "decision_stage_improvement_summary.json"),
                }
            ),
        },
        "evidence_aware_answer_synthesis": {
            "evidence_usage_audit": "outputs/reports/evidence_usage_audit.md",
            "rewrite_trial": "outputs/reports/evidence_aware_answer_rewrite_trial.md",
            "feedback_loop_final": "outputs/reports/feedback_loop_answer_synthesis_final.md",
            "sql_evidence_usage_audit": "outputs/reports/sql_evidence_usage_audit.md",
            "confidence_calibration_audit": "outputs/reports/confidence_calibration_audit.md",
            "token_efficiency_audit": "outputs/reports/token_efficiency_audit.md",
            **_evidence_answer_status(
                {
                    "evidence_usage_audit": _load_json(config.outputs_dir / "reports" / "evidence_usage_audit.json"),
                    "evidence_aware_answer_rewrite_trial": _load_json(config.outputs_dir / "reports" / "evidence_aware_answer_rewrite_trial.json"),
                    "feedback_loop_answer_synthesis_final": _load_json(config.outputs_dir / "reports" / "feedback_loop_answer_synthesis_final.json"),
                    "sql_evidence_usage_audit": _load_json(config.outputs_dir / "reports" / "sql_evidence_usage_audit.json"),
                    "confidence_calibration_audit": _load_json(config.outputs_dir / "reports" / "confidence_calibration_audit.json"),
                    "token_efficiency_audit": _load_json(config.outputs_dir / "reports" / "token_efficiency_audit.json"),
                }
            ),
        },
        "workshop_requirement_alignment": {
            "path": "outputs/reports/workshop_requirement_audit.md",
            "overall_status": _load_json(config.outputs_dir / "reports" / "workshop_requirement_audit.json")
            .get("overall_status", "unavailable"),
            "critical_failure_count": len(
                _load_json(config.outputs_dir / "reports" / "workshop_requirement_audit.json")
                .get("critical_failures", [])
            ),
        },
        "cleanup_reports": [
            "outputs/reports/cleanup_audit.md",
            "outputs/reports/cleanup_final_report.md",
            "outputs/reports/repo_cleanup_preflight.md",
            "outputs/reports/repo_cleanup_candidate_inventory.md",
            "outputs/reports/repo_cleanup_deletion_plan.md",
            "outputs/reports/repo_cleanup_result.md",
        ],
        "post_change_validation": {
            "required_commands": list(POST_CHANGE_VALIDATION_COMMANDS),
            "report_regeneration_targets": list(REPORT_REGENERATION_TARGETS),
            "skip_policy": "Skipped commands must record command, reason, substitute validation, and residual risk.",
            "final_response_must_include": [
                "files changed",
                "reports generated",
                "files deleted",
                "validation commands run and results",
                "skipped commands and reasons",
                "check_submission_ready status",
                "secret scan status",
                "SQL_FIRST_API_VERIFY unchanged confirmation",
                "final submission format unchanged confirmation",
            ],
        },
        "current_status": {
            "preferred_strategy": system["preferred_strategy"],
            "packaged_strict_score": system["packaged_strict_score"],
            "best_isolated_score": system["best_isolated_score"],
            "hidden_style": system["hidden_style"]["label"],
            "final_submission_ready": system["final_submission_ready"],
            "live_adobe_api_readiness": system["live_adobe_api_readiness"]["overall_status"],
            "post_live_robustness": system["post_live_robustness"].get("recommendation"),
            "evidence_aware_answer_synthesis": system["evidence_aware_answer_synthesis"].get("recommendation"),
            "llm_recommendation": llm["recommendation"],
            "sdk_tool_calling_optimization": system["sdk_tool_calling_optimization"].get("decision"),
            "correctness_efficiency_evaluation": system["correctness_efficiency_evaluation"].get("decision"),
            "sdk_tool_calling_efficiency_promotion": system["sdk_tool_calling_efficiency_promotion"].get("decision"),
            "core_tool_policy_optimizer": system["core_tool_policy_optimizer"].get("decision"),
            "repo_cleanup": system["repo_cleanup"].get("status"),
            "dashsys_project_skill": system["dashsys_project_skill"].get("overall_status"),
            "context7_docs_audit": system["context7_documentation_grounded_audit"].get("status"),
            "target_0_75_reached": accuracy["target_0_75_reached"],
        },
    }


def render_system_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# System Summary",
            "",
            f"- Preferred strategy: `{payload['preferred_strategy']}`",
            f"- Packaged strict score: `{payload['packaged_strict_score']}`",
            f"- Best isolated score: `{payload['best_isolated_score']}`",
            f"- Hidden-style: `{payload['hidden_style']['label']}`",
            f"- Final submission ready: `{payload['final_submission_ready']}`",
            f"- Official-token reduction enabled: `{payload['official_token_reduction_enabled']}`",
            f"- Repair execution enabled: `{payload['repair_execution_enabled']}`",
            f"- Compact context enabled: `{payload['compact_context_enabled']}`",
            f"- Final recommendation: `{payload['final_recommendation']}`",
            f"- Live Adobe API readiness: `{payload['live_adobe_api_readiness']['overall_status']}` "
            f"(smoke `{payload['live_adobe_api_readiness']['smoke_status']}`, pipeline `{payload['live_adobe_api_readiness']['pipeline_trial_status']}`)",
            f"- Live Adobe endpoint resolution: path failures remaining "
            f"`{payload['live_adobe_api_readiness'].get('endpoint_path_failures_remaining')}`; "
            f"guarded E2E `{payload['live_adobe_api_readiness'].get('guarded_live_e2e_status')}`; "
            f"go/no-go `{payload['live_adobe_api_readiness'].get('go_no_go_recommendation')}`",
            f"- Post-permission live verification: `{payload['live_adobe_api_readiness'].get('post_permission_verification_status')}`; "
            f"waiting-status report: `{payload['live_adobe_api_readiness'].get('adobe_access_waiting_status')}`",
            f"- Post-live robustness gate: `{payload['post_live_robustness'].get('recommendation')}`; "
            f"strict `{payload['post_live_robustness'].get('current_strict_score')}`; "
            f"arbitration safe `{payload['post_live_robustness'].get('arbitration_policy_safe')}`; "
            f"generated prompts `{payload['post_live_robustness'].get('generated_prompts_executed')}`",
            f"- NL-to-SQL robustness: template dependency `{payload['post_live_robustness'].get('template_dependency_score')}`; "
            f"template miss rate `{payload['post_live_robustness'].get('template_miss_rate')}`; "
            f"paraphrase consistency `{payload['post_live_robustness'].get('paraphrase_consistency_score')}`; "
            f"schema-aware fallback `{payload['post_live_robustness'].get('schema_aware_decision')}`",
            f"- LLM semantic routing helper: `{payload['llm_semantic_routing_helper']['recommendation']}` "
            f"({payload['llm_semantic_routing_helper']['status']})",
            f"- Semantic router isolated trial: `{payload['llm_semantic_routing_helper'].get('isolated_trial_status')}`; "
            f"promotion decision: `{payload['llm_semantic_routing_helper'].get('promotion_decision')}`; "
            f"packaged runtime affected: `{payload['llm_semantic_routing_helper'].get('packaged_runtime_affected')}`",
            f"- Decision-stage feedback loops: stages mapped `{payload['decision_stage_methodology'].get('stage_count')}`, "
            f"semantic-router recommendation `{payload['decision_stage_methodology'].get('semantic_router_final_recommendation')}`",
            f"- Evidence-aware answer synthesis: `{payload['evidence_aware_answer_synthesis'].get('recommendation')}` "
            f"(trial `{payload['evidence_aware_answer_synthesis'].get('trial_status')}`)",
            f"- Score-focused core path trials: `{payload['score_focused_core_path'].get('recommendation')}`; "
            f"best delta `{payload['score_focused_core_path'].get('best_strict_score_delta')}`; "
            f"runtime change applied: `{payload['score_focused_core_path'].get('runtime_change_applied')}`",
            f"- Comprehensive failure analysis: `{payload['comprehensive_failure_analysis'].get('decision')}`; "
            f"official rows `{payload['comprehensive_failure_analysis'].get('official_rows_analyzed')}`; "
            f"generated prompts `{payload['comprehensive_failure_analysis'].get('generated_prompts_analyzed')}`; "
            f"runtime change applied: `{payload['comprehensive_failure_analysis'].get('runtime_change_applied')}`",
            f"- Type-specific deterministic rules: `{payload['type_specific_deterministic_rules'].get('decision')}`; "
            f"candidate families `{payload['type_specific_deterministic_rules'].get('candidate_count')}`; "
            f"runtime change applied: `{payload['type_specific_deterministic_rules'].get('runtime_change_applied')}`",
            f"- SDK tool-calling optimization: `{payload['sdk_tool_calling_optimization'].get('decision')}`; "
            f"runtime change applied: `{payload['sdk_tool_calling_optimization'].get('runtime_change_applied')}`; "
            f"direct HTTP hits: `{payload['sdk_tool_calling_optimization'].get('direct_http_hits')}`",
            f"- Correctness + efficiency evaluation: `{payload['correctness_efficiency_evaluation'].get('decision')}`; "
            f"official overall score claim: `{payload['correctness_efficiency_evaluation'].get('official_overall_score_claim')}`; "
            f"runtime change applied: `{payload['correctness_efficiency_evaluation'].get('runtime_change_applied')}`",
            f"- SDK tool-calling efficiency promotion: `{payload['sdk_tool_calling_efficiency_promotion'].get('decision')}`; "
            f"promotion accepted: `{payload['sdk_tool_calling_efficiency_promotion'].get('promotion_accepted')}`; "
            f"direct HTTP hits: `{payload['sdk_tool_calling_efficiency_promotion'].get('direct_http_hits')}`",
            f"- Core tool policy optimizer: `{payload['core_tool_policy_optimizer'].get('decision')}`; "
            f"compiled recommendation: `{payload['core_tool_policy_optimizer'].get('compiled_recommendation')}`; "
            f"runtime change expected: `{payload['core_tool_policy_optimizer'].get('runtime_change_expected_in_repo')}`",
            f"- Repo cleanup: `{payload['repo_cleanup'].get('status')}`; "
            f"deleted paths: `{payload['repo_cleanup'].get('deleted_path_count')}`; "
            f"runtime behavior changed: `{payload['repo_cleanup'].get('runtime_behavior_changed')}`",
            f"- DASHSys Project Skill audit: `{payload['dashsys_project_skill'].get('overall_status')}`; "
            f"runtime behavior changed: `{payload['dashsys_project_skill'].get('runtime_behavior_changed')}`",
            f"- Context7 docs audit: `{payload['context7_documentation_grounded_audit'].get('status')}`; "
            f"runtime change applied: `{payload['context7_documentation_grounded_audit'].get('code_changes_applied')}`",
            "",
            "## Workflow",
            "",
            *[f"- {item}" for item in payload["workflow"]],
            "",
            "## Source Reports",
            "",
            *[f"- `{path}`" for path in payload["source_reports"]],
            "",
        ]
    )


def render_llm_summary(payload: dict[str, Any]) -> str:
    best = payload.get("best_llm_baseline") or {}
    return "\n".join(
        [
            "# LLM Baseline Summary",
            "",
            f"- Framework: `{payload['framework']}`",
            f"- Current backend/model: `{payload.get('current_backend_model')}`",
            f"- Provider/backend type: `{payload.get('provider_type')}` / `{payload.get('backend_type')}`",
            f"- Anthropic SDK support: {payload.get('anthropic_sdk_support')}",
            f"- Tool calling supported: `{payload.get('tool_calling_supported')}`",
            f"- Best LLM baseline: `{best.get('system', 'unavailable')}`",
            f"- Best LLM baseline score: `{payload.get('best_llm_baseline_score')}`",
            f"- SQL_FIRST_API_VERIFY score: `{payload.get('sql_first_api_verify_score')}`",
            f"- Recommendation: `{payload.get('recommendation')}`",
            f"- LLM semantic routing helper: `{payload['llm_semantic_routing_helper']['recommendation']}` "
            f"({payload['llm_semantic_routing_helper']['status']})",
            f"- Semantic router isolated trial: `{payload['llm_semantic_routing_helper'].get('isolated_trial_status')}`; "
            f"promotion decision: `{payload['llm_semantic_routing_helper'].get('promotion_decision')}`",
            f"- Decision-stage feedback-loop status: `{payload['decision_stage_methodology'].get('semantic_router_final_recommendation')}`",
            f"- Evidence-aware answer synthesis: `{payload['evidence_aware_answer_synthesis'].get('recommendation')}`",
            f"- SDK tool-calling optimization: `{payload['sdk_tool_calling_optimization'].get('decision')}`; "
            f"best variant `{payload['sdk_tool_calling_optimization'].get('best_variant')}`; "
            f"runtime change applied `{payload['sdk_tool_calling_optimization'].get('runtime_change_applied')}`",
            f"- Correctness + efficiency evaluation: `{payload['correctness_efficiency_evaluation'].get('decision')}`; "
            f"best candidate `{payload['correctness_efficiency_evaluation'].get('best_candidate')}`; "
            f"official overall score claim `{payload['correctness_efficiency_evaluation'].get('official_overall_score_claim')}`",
            f"- Reason: {payload.get('reason')}",
            "",
            payload["framework_note"],
            "",
        ]
    )


def render_accuracy_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Accuracy And Bottleneck Summary",
            "",
            f"- Starting score: `{payload.get('starting_score')}`",
            f"- Best isolated score: `{payload.get('best_isolated_score')}`",
            f"- 0.70 target reached: `{payload.get('target_0_70_reached')}`",
            f"- 0.75 target reached: `{payload.get('target_0_75_reached')}`",
            f"- Answer-quality bottleneck: `{payload.get('answer_quality_bottleneck')}`",
            f"- Dry-run API limitation: `{payload.get('dry_run_api_limitation')}`",
            f"- Live Adobe API readiness: `{payload['live_adobe_api_readiness']['overall_status']}`; "
            f"infrastructure validation only: `{payload['live_adobe_api_readiness']['infrastructure_validation_only']}`",
            f"- Post-live robustness gate: `{payload['post_live_robustness'].get('recommendation')}`; "
            f"strict score `{payload['post_live_robustness'].get('current_strict_score')}`; "
            f"generated diagnostic pass `{payload['post_live_robustness'].get('generated_prompt_runtime_pass_count')}`"
            f"/`{payload['post_live_robustness'].get('generated_prompts_executed')}`",
            f"- Generalization risk: template dependency `{payload['post_live_robustness'].get('template_dependency_score')}`; "
            f"template miss rate `{payload['post_live_robustness'].get('template_miss_rate')}`; "
            f"controller trial `{payload['post_live_robustness'].get('controller_rewrite_recommendation')}`",
            f"- Supportable rewrite status: `{payload.get('supportable_rewrite_status')}`",
            f"- Endpoint tie-break status: `{payload.get('endpoint_tiebreak_status')}`",
            f"- AST canary status: `{payload.get('ast_canary_status')}`",
            f"- LLM semantic routing helper: `{payload['llm_semantic_routing_helper']['recommendation']}` "
            f"({payload['llm_semantic_routing_helper']['status']})",
            f"- Semantic router isolated trial: `{payload['llm_semantic_routing_helper'].get('isolated_trial_status')}`; "
            f"promotion decision: `{payload['llm_semantic_routing_helper'].get('promotion_decision')}`",
            f"- Decision-stage feedback-loop status: `{payload['decision_stage_methodology'].get('semantic_router_final_recommendation')}`",
            f"- Evidence-aware answer synthesis: `{payload['evidence_aware_answer_synthesis'].get('recommendation')}`; "
            f"answer-only invariant enforced: `{payload['evidence_aware_answer_synthesis'].get('answer_only_invariant_enforced')}`",
            f"- Score-focused core path trials: `{payload['score_focused_core_path'].get('recommendation')}`; "
            f"best strict delta `{payload['score_focused_core_path'].get('best_strict_score_delta')}`; "
            f"runtime change applied `{payload['score_focused_core_path'].get('runtime_change_applied')}`",
            f"- Comprehensive failure analysis: `{payload['comprehensive_failure_analysis'].get('decision')}`; "
            f"rule candidates `{payload['comprehensive_failure_analysis'].get('candidate_count')}`; "
            f"runtime change applied `{payload['comprehensive_failure_analysis'].get('runtime_change_applied')}`",
            f"- Type-specific deterministic rules: `{payload['type_specific_deterministic_rules'].get('decision')}`; "
            f"candidate families `{payload['type_specific_deterministic_rules'].get('candidate_count')}`; "
            f"runtime change applied `{payload['type_specific_deterministic_rules'].get('runtime_change_applied')}`",
            f"- SDK tool-calling optimization: `{payload['sdk_tool_calling_optimization'].get('decision')}`; "
            f"best projected strict delta `{payload['sdk_tool_calling_optimization'].get('strict_score_delta_projected')}`; "
            f"runtime change applied `{payload['sdk_tool_calling_optimization'].get('runtime_change_applied')}`",
            f"- Correctness + efficiency evaluation: `{payload['correctness_efficiency_evaluation'].get('decision')}`; "
            f"best candidate `{payload['correctness_efficiency_evaluation'].get('best_candidate')}`; "
            f"runtime change applied `{payload['correctness_efficiency_evaluation'].get('runtime_change_applied')}`",
            f"- SDK tool-calling efficiency promotion: `{payload['sdk_tool_calling_efficiency_promotion'].get('decision')}`; "
            f"promotion accepted `{payload['sdk_tool_calling_efficiency_promotion'].get('promotion_accepted')}`; "
            f"runtime change applied `{payload['sdk_tool_calling_efficiency_promotion'].get('runtime_change_applied')}`",
            f"- Core tool policy optimizer: `{payload['core_tool_policy_optimizer'].get('decision')}`; "
            f"strict after projected `{payload['core_tool_policy_optimizer'].get('strict_score_after_projected')}`; "
            f"runtime change expected `{payload['core_tool_policy_optimizer'].get('runtime_change_expected_in_repo')}`",
            "",
            "## Why Changes Remain Shadow-Only",
            "",
            *[f"- {item}" for item in payload["why_shadow_only"]],
            "",
        ]
    )


def render_visualization_summary(payload: dict[str, Any]) -> str:
    mapping = payload["prompt_to_sql_mapping"]
    return "\n".join(
        [
            "# Visualization Summary",
            "",
            f"- Primary example: `{payload['primary_example']}`",
            f"- Raw prompt: {payload['raw_prompt']}",
            f"- Main storyboard: `{payload['main_storyboard']}`",
            f"- End-to-end system dataflow: `{payload['end_to_end_system_dataflow']}`",
            f"- Single SVG project overview: `{payload['single_svg_project_overview']}`",
            f"- Secondary reference: {payload['secondary_reference']}",
            "",
            "## Prompt To SQL Mapping",
            "",
            f"- `schemas` → `{mapping['schemas']}`",
            f"- `how many` → `{mapping['how_many']}`",
            f"- `{mapping['identifier_column']}` → `{mapping['result']}`",
            "",
        ]
    )


def render_report_index(payload: dict[str, Any]) -> str:
    lines = [
        "# Consolidated Report Index",
        "",
        payload["message"],
        "",
        "## Canonical Reports",
        "",
    ]
    lines.extend(f"- [{Path(path).name}]({Path(path).name})" for path in payload["canonical_reports"])
    lines.extend(["", "## Key Source-Of-Truth Reports", ""])
    lines.extend(f"- `{path}`" for path in payload["key_source_of_truth_reports"])
    lines.extend(["", "## Key Visualizations", ""])
    for path in payload["key_visualizations"]:
        if path.startswith("outputs/visualizations/"):
            href = f"../visualizations/{Path(path).name}"
            lines.append(f"- [{path}]({href})")
        else:
            lines.append(f"- `{path}`")
    lines.extend(["", "## Diagnostic Prompt Coverage", ""])
    for item in payload.get("diagnostic_prompt_coverage", []):
        lines.append(f"- `{item['path']}` - {item['label']}")
    lines.extend(["", "## Post-Live Robustness Gate", ""])
    robustness = payload.get("post_live_robustness", {})
    lines.append(f"- Preflight: `{robustness.get('preflight_path')}`")
    lines.append(f"- Arbitration guard: `{robustness.get('arbitration_guard_path')}`")
    lines.append(f"- Full generated suite: `{robustness.get('full_generated_suite_path')}`")
    lines.append(f"- NL-to-SQL robustness: `{robustness.get('nl_sql_robustness_path')}`")
    lines.append(f"- Paraphrase consistency: `{robustness.get('paraphrase_consistency_path')}`")
    lines.append(f"- Schema-aware failure decomposition: `{robustness.get('schema_aware_failure_decomposition_path')}`")
    lines.append(f"- Schema-aware feedback loop: `{robustness.get('schema_aware_feedback_loop_path')}`")
    lines.append(f"- LLM trace decomposition: `{robustness.get('llm_trace_decomposition_path')}`")
    lines.append(f"- Controller rewrite trial: `{robustness.get('controller_rewrite_trial_path')}`")
    lines.append(f"- Multi-LLM robustness: `{robustness.get('multi_llm_robustness_path')}`")
    lines.append(f"- Live tool efficiency: `{robustness.get('live_tool_efficiency_path')}`")
    lines.append(f"- Integrated gate: `{robustness.get('integrated_gate_path')}`")
    lines.append(f"- Recommendation: `{robustness.get('recommendation')}`")
    lines.append(f"- Current strict score: `{robustness.get('current_strict_score')}`")
    lines.append(f"- Generated diagnostic prompts executed: `{robustness.get('generated_prompts_executed')}`")
    lines.append(f"- Template dependency score: `{robustness.get('template_dependency_score')}`")
    lines.append(f"- Schema-aware fallback decision: `{robustness.get('schema_aware_decision')}`")
    lines.extend(["", "## LLM Controller Diagnostics", ""])
    controller = payload.get("llm_controller_diagnostics", {})
    lines.append(f"- Failure decomposition: `{controller.get('failure_decomposition_path')}`")
    lines.append(f"- Rewrite ablation: `{controller.get('rewrite_ablation_path')}`")
    lines.append(f"- Controller status: `{controller.get('controller_status')}`")
    lines.append(f"- Automatic promotion: `{controller.get('automatic_promotion')}`")
    lines.append(f"- Recommendation: `{controller.get('recommendation')}`")
    lines.extend(["", "## System-Wide SDK LLM Audit", ""])
    audit = payload.get("sdk_usage_audit", {})
    lines.append(f"- `{audit.get('path')}`")
    lines.append(f"- Runtime LLM direct HTTP hits: `{audit.get('runtime_llm_direct_http_hits')}`")
    lines.extend(["", "## SDK Tool Calling Optimization", ""])
    sdk_opt = payload.get("sdk_tool_calling_optimization", {})
    lines.append(f"- Preflight: `{sdk_opt.get('preflight_path')}`")
    lines.append(f"- Tool-call surface audit: `{sdk_opt.get('surface_audit_path')}`")
    lines.append(f"- Decision analysis: `{sdk_opt.get('decision_analysis_path')}`")
    lines.append(f"- Variants: `{sdk_opt.get('variants_path')}`")
    lines.append(f"- Isolated trials: `{sdk_opt.get('trials_path')}`")
    lines.append(f"- Fix decision: `{sdk_opt.get('fix_decision_path')}`")
    lines.append(f"- Decision: `{sdk_opt.get('decision')}`")
    lines.append(f"- Runtime change applied: `{sdk_opt.get('runtime_change_applied')}`")
    lines.append(f"- Direct HTTP hits: `{sdk_opt.get('direct_http_hits')}`")
    lines.append("- These reports are shadow-only SDK/tool-call policy analysis; SQL_FIRST_API_VERIFY remains packaged default.")
    lines.extend(["", "## Correctness + Efficiency Evaluation", ""])
    ce = payload.get("correctness_efficiency_evaluation", {})
    lines.append(f"- Scorecard: `{ce.get('scorecard_path')}`")
    lines.append(f"- Fix decision: `{ce.get('fix_decision_path')}`")
    lines.append(f"- Decision: `{ce.get('decision')}`")
    lines.append(f"- Best candidate: `{ce.get('best_candidate')}`")
    lines.append(f"- Official overall score claim: `{ce.get('official_overall_score_claim')}`")
    lines.append(f"- Organizer weights known: `{ce.get('organizer_weights_known')}`")
    lines.append(f"- Runtime change applied: `{ce.get('runtime_change_applied')}`")
    lines.append("- Correctness-only strict score is not treated as the full organizer evaluation picture.")
    lines.extend(["", "## SDK Tool Calling Efficiency Promotion", ""])
    sdk_promo = payload.get("sdk_tool_calling_efficiency_promotion", {})
    lines.append(f"- Preflight: `{sdk_promo.get('preflight_path')}`")
    lines.append(f"- Plan: `{sdk_promo.get('plan_path')}`")
    lines.append(f"- Decision: `{sdk_promo.get('decision_path')}`")
    lines.append(f"- Decision status: `{sdk_promo.get('decision')}`")
    lines.append(f"- Runtime change applied: `{sdk_promo.get('runtime_change_applied')}`")
    lines.append(f"- Promotion accepted: `{sdk_promo.get('promotion_accepted')}`")
    lines.append(f"- Direct HTTP hits: `{sdk_promo.get('direct_http_hits')}`")
    lines.append("- This is a speed-only SDK/tool-call patch; SQL_FIRST_API_VERIFY remains the packaged default.")
    lines.extend(["", "## Core Tool Policy Optimizer", ""])
    core = payload.get("core_tool_policy_optimizer", {})
    lines.append(f"- Tool audit: `{core.get('audit_path')}`")
    lines.append(f"- Search space: `{core.get('search_space_path')}`")
    lines.append(f"- Optimizer: `{core.get('optimizer_path')}`")
    lines.append(f"- Search results: `{core.get('search_results_path')}`")
    lines.append(f"- execute_sql candidates: `{core.get('execute_sql_candidates_path')}`")
    lines.append(f"- call_api candidates: `{core.get('call_api_candidates_path')}`")
    lines.append(f"- Compiled candidate: `{core.get('compiled_candidate_path')}`")
    lines.append(f"- Promotion decision: `{core.get('promotion_decision_path')}`")
    lines.append(f"- Decision: `{core.get('decision')}`")
    lines.append(f"- Runtime change expected in repo: `{core.get('runtime_change_expected_in_repo')}`")
    lines.append("- This optimizer is restricted to execute_sql/call_api internals; SQL_FIRST_API_VERIFY remains packaged default.")
    lines.extend(["", "## DASHSys Project Skill", ""])
    dashsys_skill = payload.get("dashsys_project_skill", {})
    lines.append(f"- Skill: `{dashsys_skill.get('skill_path')}`")
    lines.append(f"- Audit: `{dashsys_skill.get('audit_path')}`")
    lines.append(f"- Overall status: `{dashsys_skill.get('overall_status')}`")
    lines.append(f"- Runtime behavior changed: `{dashsys_skill.get('runtime_behavior_changed')}`")
    lines.append(f"- Env local accessed: `{dashsys_skill.get('env_local_accessed')}`")
    lines.append("- Use this repo-local Skill before serious Codex changes; it separates correctness, efficiency, live API, reporting, packaging, and security work.")
    lines.extend(["", "## Context7 Documentation-Grounded Audit", ""])
    context7 = payload.get("context7_documentation_grounded_audit", {})
    lines.append(f"- Preflight: `{context7.get('preflight_path')}`")
    lines.append(f"- Dependency docs summary: `{context7.get('docs_summary_path')}`")
    lines.append(f"- Code alignment audit: `{context7.get('code_alignment_path')}`")
    lines.append(f"- Fix decision: `{context7.get('fix_decision_path')}`")
    lines.append(f"- Status: `{context7.get('status')}`")
    lines.append(f"- Dependencies reviewed: `{context7.get('dependency_count')}`")
    lines.append(f"- Code changes applied: `{context7.get('code_changes_applied')}`")
    lines.append("- External SDK/API changes require Context7 documentation lookup first; Context7 secrets must never be printed.")
    lines.extend(["", "## Score-Focused Direct Path Trials", ""])
    score_path = payload.get("score_focused_core_path", {})
    lines.append(f"- Contribution audit: `{score_path.get('contribution_audit_path')}`")
    lines.append(f"- Isolated trials: `{score_path.get('trials_path')}`")
    lines.append(f"- Fix decision: `{score_path.get('fix_decision_path')}`")
    lines.append(f"- Recommendation: `{score_path.get('recommendation')}`")
    lines.append(f"- Best strict delta: `{score_path.get('best_strict_score_delta')}`")
    lines.append(f"- Runtime change applied: `{score_path.get('runtime_change_applied')}`")
    lines.append("- These reports use the SVG only as a score-path map; visualization changes are not score improvements.")
    lines.extend(["", "## Comprehensive Failure Analysis", ""])
    comprehensive = payload.get("comprehensive_failure_analysis", {})
    lines.append(f"- Preflight: `{comprehensive.get('preflight_path')}`")
    lines.append(f"- Official row table: `{comprehensive.get('official_row_failure_table_path')}`")
    lines.append(f"- Generated prompt table: `{comprehensive.get('generated_prompt_failure_table_path')}`")
    lines.append(f"- Cross-dataset clusters: `{comprehensive.get('cross_dataset_clusters_path')}`")
    lines.append(f"- Rule candidates: `{comprehensive.get('rule_candidates_path')}`")
    lines.append(f"- Hardcoding risk audit: `{comprehensive.get('hardcoding_risk_audit_path')}`")
    lines.append(f"- Fix decision: `{comprehensive.get('fix_decision_path')}`")
    lines.append(f"- Decision: `{comprehensive.get('decision')}`")
    lines.append(f"- Runtime change applied: `{comprehensive.get('runtime_change_applied')}`")
    lines.append(f"- Generated prompts used for: `{comprehensive.get('generated_prompts_used_for')}`")
    lines.append("- Official strict rows diagnose real score loss; generated prompts provide coverage/generalization evidence only.")
    lines.extend(["", "## Type-Specific Deterministic Rules", ""])
    type_rules = payload.get("type_specific_deterministic_rules", {})
    lines.append(f"- Prompt-type audit: `{type_rules.get('prompt_type_audit_path')}`")
    lines.append(f"- Rule candidates: `{type_rules.get('rule_candidates_path')}`")
    lines.append(f"- Isolated trials: `{type_rules.get('rule_trials_path')}`")
    lines.append(f"- Fix decision: `{type_rules.get('fix_decision_path')}`")
    lines.append(f"- Decision: `{type_rules.get('decision')}`")
    lines.append(f"- Candidate count: `{type_rules.get('candidate_count')}`")
    lines.append(f"- Trial count: `{type_rules.get('trial_count')}`")
    lines.append(f"- Runtime change applied: `{type_rules.get('runtime_change_applied')}`")
    lines.append("- Rules are grouped by prompt type, domain, answer intent, execution need, and evidence shape.")
    lines.extend(["", "## Live Adobe API Readiness", ""])
    live = payload.get("live_adobe_api_readiness", {})
    lines.append(f"- Readiness audit: `{live.get('audit_path')}`")
    lines.append(f"- API_REQUIRED readiness matrix: `{live.get('api_required_readiness_matrix_path')}`")
    lines.append(f"- Smoke report: `{live.get('smoke_path')}`")
    lines.append(f"- Endpoint path diagnosis: `{live.get('endpoint_path_diagnosis_path')}`")
    lines.append(f"- External blockers: `{live.get('external_blockers_path')}`")
    lines.append(f"- Follow-up commands: `{live.get('followup_commands_path')}`")
    lines.append(f"- Full-run blocker: `{live.get('full_run_blocker_path')}`")
    lines.append(f"- Post-permission verification: `{live.get('post_permission_verification_path')}`")
    lines.append(f"- Adobe access waiting status: `{live.get('adobe_access_waiting_status_path')}`")
    lines.append(f"- Evidence pipeline trial: `{live.get('pipeline_trial_path')}`")
    lines.append(f"- Mock live evidence pipeline trial: `{live.get('mock_pipeline_trial_path')}`")
    lines.append(f"- Overall status: `{live.get('overall_status')}`")
    lines.append(f"- Credentials present in latest smoke: `{live.get('credentials_present')}`")
    lines.append(f"- Live mode attempted: `{live.get('live_mode_attempted')}`")
    lines.append(f"- Full live strict eval blocked: `{live.get('full_live_eval_blocked')}`")
    lines.append(f"- Full generated prompt suite blocked: `{live.get('full_generated_prompt_suite_blocked')}`")
    lines.append(f"- Mock parser success count: `{live.get('mock_parser_success_count')}`")
    lines.append(f"- Mock discovery chains simulated: `{live.get('mock_discovery_chain_simulated_count')}`")
    lines.append("- Live API readiness is infrastructure validation only; it is not official strict-score evidence.")
    lines.append("- `API_REQUIRED` remains required in live mode; dry-run remains an honest fallback when credentials are missing.")
    lines.extend(["", "## LLM Semantic Routing Helper", ""])
    semantic = payload.get("llm_semantic_routing_helper", {})
    lines.append(f"- `{semantic.get('path')}`")
    lines.append("- Feature flag default: `off`")
    lines.append("- Shadow-only by default: `true`")
    lines.append("- Uses SDK-based `LLMClient`; no direct HTTP; routing hints only; no final answers.")
    lines.append(f"- Status: `{semantic.get('status')}`")
    lines.append(f"- Isolated trial: `{semantic.get('isolated_trial_status')}`")
    lines.append(f"- Isolated trial report: `{semantic.get('isolated_trial_path')}`")
    lines.append(f"- Promotion decision report: `{semantic.get('promotion_decision_path')}`")
    lines.append(f"- Packaged runtime affected: `{semantic.get('packaged_runtime_affected')}`")
    lines.append(f"- Recommendation: `{semantic.get('recommendation')}`")
    lines.extend(["", "## Decision-Stage Audit And Feedback Loops", ""])
    decision = payload.get("decision_stage_audit_and_feedback_loops", {})
    lines.append(f"- Workflow decision map: `{decision.get('workflow_decision_map')}`")
    lines.append(f"- Workflow decision audit: `{decision.get('workflow_decision_audit')}`")
    lines.append(f"- Feedback-loop index: `{decision.get('feedback_loop_index')}`")
    lines.append(f"- Semantic-router loop final: `{decision.get('semantic_router_feedback_loop_final')}`")
    lines.append(f"- Decision-stage improvement summary: `{decision.get('decision_stage_improvement_summary')}`")
    lines.append(f"- Stages mapped: `{decision.get('stage_count')}`")
    lines.append(f"- Audited rows: `{decision.get('audited_query_count')}`")
    lines.append(f"- Semantic-router feedback recommendation: `{decision.get('semantic_router_final_recommendation')}`")
    lines.append("- Generated diagnostic prompts remain coverage-only and are not promotion evidence.")
    lines.extend(["", "## Evidence-Aware Answer Synthesis", ""])
    evidence = payload.get("evidence_aware_answer_synthesis", {})
    lines.append(f"- Evidence usage audit: `{evidence.get('evidence_usage_audit')}`")
    lines.append(f"- Answer rewrite trial: `{evidence.get('rewrite_trial')}`")
    lines.append(f"- Feedback-loop final: `{evidence.get('feedback_loop_final')}`")
    lines.append(f"- SQL evidence usage audit: `{evidence.get('sql_evidence_usage_audit')}`")
    lines.append(f"- Confidence calibration audit: `{evidence.get('confidence_calibration_audit')}`")
    lines.append(f"- Token efficiency audit: `{evidence.get('token_efficiency_audit')}`")
    lines.append(f"- Trial status: `{evidence.get('trial_status')}`")
    lines.append(f"- Recommendation: `{evidence.get('recommendation')}`")
    lines.append(f"- Answer-only invariant enforced: `{evidence.get('answer_only_invariant_enforced')}`")
    lines.append("- Answer-only promotion requires invariant SQL/API/tool/evidence hashes, hidden-style 48/48, readiness pass, and no unsupported-claim increase.")
    lines.extend(["", "## Workshop Requirement Alignment", ""])
    workshop = payload.get("workshop_requirement_alignment", {})
    lines.append(f"- [{Path(str(workshop.get('path'))).name}]({Path(str(workshop.get('path'))).name})")
    lines.append(f"- Overall status: `{workshop.get('overall_status')}`")
    lines.append(f"- Critical failures: `{workshop.get('critical_failure_count')}`")
    lines.extend(["", "## Cleanup Reports", ""])
    lines.extend(f"- `{path}`" for path in payload.get("cleanup_reports", []))
    lines.extend(["", "## Post-Change Validation Contract", ""])
    lines.append(payload["post_change_validation"]["skip_policy"])
    lines.extend(["", "Required commands:"])
    lines.extend(f"- `{command}`" for command in payload["post_change_validation"]["required_commands"])
    lines.extend(["", "Regenerated report surfaces:"])
    lines.extend(f"- `{path}`" for path in payload["post_change_validation"]["report_regeneration_targets"])
    lines.extend(["", "## Current Status", ""])
    for key, value in payload["current_status"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sql_first_metrics(sources: dict[str, Any]) -> dict[str, Any]:
    return (
        sources.get("eval_results_strict", {})
        .get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
    )


def _best_isolated_score(sources: dict[str, Any]) -> float | str:
    candidates = [
        sources["autonomous_trial"].get("summary", {}).get("strict_final_score"),
        sources["autonomous_score_push"].get("summary", {}).get("best_achieved_score"),
        sources["score075_blocker"].get("best_achieved_score"),
    ]
    numbers = [float(value) for value in candidates if isinstance(value, (int, float))]
    return round(max(numbers), 4) if numbers else "unavailable"


def _hidden_label(summary: dict[str, Any]) -> str:
    passed = summary.get("passed_cases")
    total = summary.get("total_cases")
    if passed is None or total is None:
        return "unavailable"
    return f"{passed}/{total}"


def _best_llm_strategy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        row for row in rows
        if isinstance(row.get("strict_score", row.get("strict_final_score")), (int, float))
    ]
    if not scored:
        return {"system": "unavailable", "strict_score": "unavailable"}
    best = max(scored, key=lambda row: float(row.get("strict_score", row.get("strict_final_score"))))
    return {
        "system": best.get("system"),
        "strict_score": best.get("strict_score", best.get("strict_final_score")),
        "strict_correctness": best.get("strict_correctness"),
    }


def _status_from_report(report: dict[str, Any], default: str) -> str:
    summary = report.get("summary", {})
    return (
        summary.get("recommendation")
        or report.get("recommendation")
        or ("shadow_only" if report.get("shadow_only") else None)
        or default
    )


def _semantic_router_status(sources: dict[str, Any]) -> dict[str, Any]:
    report = sources.get("llm_semantic_router") or {}
    isolated = sources.get("llm_semantic_router_isolated") or {}
    promotion = sources.get("llm_semantic_router_promotion") or {}
    status = report.get("status") or "not_run"
    recommendation = promotion.get("decision") or isolated.get("recommendation") or report.get("recommendation") or "keep_disabled"
    return {
        "status": status,
        "feature_flag_default": "off",
        "shadow_only_default": True,
        "sdk_based": True,
        "direct_http_allowed": False,
        "final_answer_generation": False,
        "routing_hints_only": True,
        "packaged_runtime_affected": False,
        "helper_called_prompts": report.get("helper_called_prompts", 0),
        "valid_helper_outputs": report.get("valid_helper_outputs", 0),
        "rejected_helper_outputs": report.get("rejected_helper_outputs", 0),
        "normalization_actions_count": report.get("normalization_actions_count", 0),
        "synonym_mappings_coerced_count": report.get("synonym_mappings_coerced_count", 0),
        "domain_aliases_applied_count": report.get("domain_aliases_applied_count", 0),
        "isolated_trial_status": isolated.get("status", "not_run"),
        "isolated_trial_strict_delta": isolated.get("strict_score_delta"),
        "isolated_trial_recommendation": isolated.get("recommendation"),
        "promotion_decision": promotion.get("decision", "not_run"),
        "recommendation": recommendation,
        "source_report": "outputs/reports/llm_semantic_router_shadow_eval.md",
        "isolated_trial_source_report": "outputs/reports/llm_semantic_router_isolated_trial.md",
        "promotion_decision_source_report": "outputs/reports/llm_semantic_router_promotion_decision.md",
    }


def _decision_stage_status(sources: dict[str, Any]) -> dict[str, Any]:
    decision_map = sources.get("workflow_decision_map") or {}
    audit = sources.get("workflow_decision_audit") or {}
    final = sources.get("feedback_loop_semantic_router_final") or {}
    summary = sources.get("decision_stage_improvement_summary") or {}
    return {
        "stage_count": decision_map.get("stage_count", "not_run"),
        "audited_query_count": audit.get("total_queries", "not_run"),
        "top_bottlenecks": audit.get("bottleneck_distribution", {}),
        "feedback_loop_candidate_count": len((sources.get("improvement_feedback_loop_index") or {}).get("candidates", [])),
        "semantic_router_iteration_count": final.get("iteration_count", "not_run"),
        "semantic_router_final_recommendation": final.get("final_recommendation", "not_run"),
        "packaged_runtime_changed": summary.get("packaged_runtime_changed", False),
        "source_reports": [
            "outputs/reports/workflow_decision_map.md",
            "outputs/reports/workflow_decision_audit.md",
            "outputs/reports/improvement_feedback_loop_index.md",
            "outputs/reports/feedback_loop_semantic_router_final.md",
            "outputs/reports/decision_stage_improvement_summary.md",
        ],
    }


def _score_path_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("score_path_contribution_audit") or {}
    trials = sources.get("score_focused_core_improvement_trials") or {}
    decision = sources.get("score_focused_core_fix_decision") or {}
    summary = trials.get("summary") or {}
    return {
        "contribution_audit_status": "complete" if audit.get("report_type") == "score_path_contribution_audit" else "not_run",
        "trial_status": "complete" if trials.get("report_type") == "score_focused_core_improvement_trials" else "not_run",
        "fix_decision_status": "complete" if decision.get("report_type") == "score_focused_core_fix_decision" else "not_run",
        "primary_score_focus": (audit.get("conclusions") or {}).get("primary_score_focus", []),
        "baseline_strict_score": summary.get("baseline_strict_score") or decision.get("baseline_strict_score"),
        "best_variant": summary.get("best_variant") or decision.get("best_variant"),
        "best_strict_score_delta": summary.get("best_strict_score_delta") or decision.get("best_strict_score_delta"),
        "recommendation": decision.get("recommendation") or summary.get("recommendation", "not_run"),
        "promotion_safe": bool(decision.get("promotion_safe", False)),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", False)),
        "final_submission_changed": bool(decision.get("final_submission_changed", False)),
        "packaged_runtime_affected": False,
        "source_reports": [
            "outputs/reports/score_path_contribution_audit.md",
            "outputs/reports/score_focused_core_improvement_trials.md",
            "outputs/reports/score_focused_core_fix_decision.md",
        ],
    }


def _comprehensive_failure_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("comprehensive_failure_analysis_preflight") or {}
    official = sources.get("official_row_failure_table") or {}
    generated = sources.get("generated_prompt_failure_table") or {}
    clusters = sources.get("cross_dataset_failure_clusters") or {}
    candidates = sources.get("general_deterministic_rule_candidates") or {}
    hardcoding = sources.get("general_rule_hardcoding_risk_audit") or {}
    decision = sources.get("comprehensive_failure_fix_decision") or {}
    official_summary = official.get("summary") or {}
    generated_summary = generated.get("summary") or {}
    candidate_rows = candidates.get("candidates") or []
    cluster_rows = clusters.get("clusters") or []
    return {
        "preflight_status": "complete" if preflight.get("report_type") == "comprehensive_failure_analysis_preflight" else "not_run",
        "official_table_status": "complete" if official.get("report_type") == "official_row_failure_table" else "not_run",
        "generated_table_status": "complete" if generated.get("report_type") == "generated_prompt_failure_table" else "not_run",
        "cluster_status": "complete" if clusters.get("report_type") == "cross_dataset_failure_clusters" else "not_run",
        "candidate_status": "complete" if candidates.get("report_type") == "general_deterministic_rule_candidates" else "not_run",
        "hardcoding_audit_status": "complete" if hardcoding.get("report_type") == "general_rule_hardcoding_risk_audit" else "not_run",
        "decision_status": "complete" if decision.get("report_type") == "comprehensive_failure_fix_decision" else "not_run",
        "decision": decision.get("decision", "not_run"),
        "official_rows_analyzed": decision.get("total_official_rows_analyzed", official_summary.get("total_rows")),
        "generated_prompts_analyzed": decision.get("total_generated_prompts_analyzed", generated_summary.get("total_prompts")),
        "rows_requiring_adobe_access": decision.get("rows_requiring_adobe_access", official_summary.get("requires_live_api_rows")),
        "prompts_requiring_live_api": decision.get("prompts_requiring_live_api", generated_summary.get("requires_live_api_prompts")),
        "candidate_count": len(candidate_rows),
        "cluster_count": len(cluster_rows),
        "strongest_candidate_rule": decision.get("strongest_candidate_rule"),
        "hardcoding_audit_passed": decision.get("hardcoding_audit_passed", hardcoding.get("all_candidates_pass_hardcoding_audit")),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", False)),
        "final_submission_changed": bool(decision.get("final_submission_changed", False)),
        "official_rows_used_for": "real_score_loss_diagnosis",
        "generated_prompts_used_for": "generality_and_coverage_only",
        "source_reports": [
            "outputs/reports/comprehensive_failure_analysis_preflight.md",
            "outputs/reports/official_row_failure_table.md",
            "outputs/reports/generated_prompt_failure_table.md",
            "outputs/reports/cross_dataset_failure_clusters.md",
            "outputs/reports/general_deterministic_rule_candidates.md",
            "outputs/reports/cross_dataset_counterfactual_answer_sketches.md",
            "outputs/reports/general_rule_hardcoding_risk_audit.md",
            "outputs/reports/comprehensive_failure_fix_decision.md",
        ],
    }


def _type_specific_rule_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("deterministic_prompt_type_audit") or {}
    candidates = sources.get("type_specific_deterministic_rule_candidates") or {}
    trials = sources.get("type_specific_deterministic_rule_trials") or {}
    decision = sources.get("type_specific_rule_fix_decision") or {}
    summary = trials.get("summary") or {}
    return {
        "prompt_type_audit_status": "complete" if audit.get("report_type") == "deterministic_prompt_type_audit" else "not_run",
        "candidate_status": "complete" if candidates.get("report_type") == "type_specific_deterministic_rule_candidates" else "not_run",
        "trial_status": "complete" if trials.get("report_type") == "type_specific_deterministic_rule_trials" else "not_run",
        "decision_status": "complete" if decision.get("report_type") == "type_specific_rule_fix_decision" else "not_run",
        "decision": decision.get("decision", "not_run"),
        "official_row_count": audit.get("official_row_count"),
        "generated_prompt_count": audit.get("generated_prompt_count"),
        "bucket_count": (audit.get("summary") or {}).get("bucket_count"),
        "fast_path_possible_buckets": (audit.get("summary") or {}).get("fast_path_possible_buckets"),
        "candidate_count": len(candidates.get("candidates") or []),
        "trial_count": len(trials.get("trial_reports") or []),
        "best_rule_family": summary.get("best_rule_family"),
        "best_strict_score_delta": summary.get("best_strict_score_delta"),
        "total_api_dry_run_call_reduction": summary.get("total_api_dry_run_call_reduction"),
        "safe_for_promotion_count": summary.get("safe_for_promotion_count"),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", trials.get("runtime_change_applied", False))),
        "final_submission_changed": bool(decision.get("final_submission_changed", False)),
        "generated_prompts_used_for": "generality_and_speed_evidence_only",
        "source_reports": [
            "outputs/reports/deterministic_prompt_type_audit.md",
            "outputs/reports/type_specific_deterministic_rule_candidates.md",
            "outputs/reports/type_specific_deterministic_rule_trials.md",
            "outputs/reports/type_specific_rule_fix_decision.md",
        ],
    }


def _sdk_tool_calling_optimization_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("sdk_tool_calling_optimization_preflight") or {}
    surface = sources.get("sdk_tool_call_surface_audit") or {}
    decision_analysis = sources.get("sdk_tool_call_decision_analysis") or {}
    variants = sources.get("sdk_tool_call_optimization_variants") or {}
    trials = sources.get("sdk_tool_calling_optimization_trials") or {}
    fix_decision = sources.get("sdk_tool_calling_fix_decision") or {}
    trial_summary = trials.get("summary") or {}
    return {
        "preflight_status": "complete" if preflight.get("report_type") == "sdk_tool_calling_optimization_preflight" else "not_run",
        "surface_audit_status": "complete" if surface.get("report_type") == "sdk_tool_call_surface_audit" else "not_run",
        "decision_analysis_status": "complete" if decision_analysis.get("report_type") == "sdk_tool_call_decision_analysis" else "not_run",
        "variants_status": "complete" if variants.get("report_type") == "sdk_tool_call_optimization_variants" else "not_run",
        "trial_status": "complete" if trials.get("report_type") == "sdk_tool_calling_optimization_trials" else "not_run",
        "fix_decision_status": "complete" if fix_decision.get("report_type") == "sdk_tool_calling_fix_decision" else "not_run",
        "decision": fix_decision.get("decision", "not_run"),
        "best_variant": fix_decision.get("best_variant") or trial_summary.get("best_variant"),
        "strict_score_before": fix_decision.get("strict_score_before") or trials.get("baseline_strict_score"),
        "strict_score_delta_projected": fix_decision.get("strict_score_delta_projected"),
        "variant_count": len(variants.get("variants") or trials.get("variants") or []),
        "speed_safe_candidate_count": trial_summary.get("speed_safe_candidate_count"),
        "promotion_safe": bool(fix_decision.get("promotion_safe", False)),
        "runtime_change_applied": bool(fix_decision.get("runtime_change_applied", False)),
        "final_submission_format_changed": bool(fix_decision.get("final_submission_format_changed", False)),
        "direct_http_hits": fix_decision.get("direct_http_hits", preflight.get("sdk_direct_http_hits")),
        "generated_prompts_used_for": "diagnostic_only_generality_evidence",
        "packaged_runtime_affected": False,
        "source_reports": [
            "outputs/reports/sdk_tool_calling_optimization_preflight.md",
            "outputs/reports/sdk_tool_call_surface_audit.md",
            "outputs/reports/sdk_tool_call_decision_analysis.md",
            "outputs/reports/sdk_tool_call_optimization_variants.md",
            "outputs/reports/sdk_tool_calling_optimization_trials.md",
            "outputs/reports/sdk_tool_calling_fix_decision.md",
        ],
    }


def _correctness_efficiency_status(sources: dict[str, Any]) -> dict[str, Any]:
    scorecard = sources.get("correctness_efficiency_scorecard") or {}
    decision = sources.get("correctness_efficiency_fix_decision") or {}
    baseline = scorecard.get("baseline") or {}
    variants = scorecard.get("variants") or []
    pareto_count = sum(1 for row in variants if row.get("pareto_dominates_baseline"))
    return {
        "scorecard_status": "complete" if scorecard.get("report_type") == "correctness_efficiency_scorecard" else "not_run",
        "fix_decision_status": "complete" if decision.get("report_type") == "correctness_efficiency_fix_decision" else "not_run",
        "decision": decision.get("decision", "not_run"),
        "best_candidate": decision.get("best_candidate"),
        "baseline_correctness_score": baseline.get("correctness_score") or decision.get("baseline_correctness_score"),
        "baseline_strict_final_score": baseline.get("strict_final_score") or decision.get("baseline_strict_final_score"),
        "variant_count": len(variants),
        "pareto_dominating_variant_count": pareto_count,
        "organizer_weights_known": bool(scorecard.get("organizer_weights_known", False)),
        "official_overall_score_claim": bool(scorecard.get("official_overall_score_claim", False)),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", False)),
        "final_submission_format_changed": bool(decision.get("final_submission_format_changed", False)),
        "source_reports": [
            "outputs/reports/correctness_efficiency_scorecard.md",
            "outputs/reports/correctness_efficiency_fix_decision.md",
        ],
    }


def _sdk_tool_calling_efficiency_promotion_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("sdk_tool_calling_promotion_preflight") or {}
    plan = sources.get("sdk_tool_calling_promotion_plan") or {}
    decision = sources.get("sdk_tool_calling_efficiency_promotion_decision") or {}
    return {
        "preflight_status": "complete" if preflight.get("report_type") == "sdk_tool_calling_promotion_preflight" else "not_run",
        "plan_status": "complete" if plan.get("report_type") == "sdk_tool_calling_promotion_plan" else "not_run",
        "decision_status": "complete" if decision.get("report_type") == "sdk_tool_calling_efficiency_promotion_decision" else "not_run",
        "decision": decision.get("decision", "not_run"),
        "selected_candidate": decision.get("selected_candidate") or preflight.get("selected_candidate"),
        "promotion_type": decision.get("promotion_type") or preflight.get("promotion_type"),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", False)),
        "promotion_accepted": bool(decision.get("promotion_accepted", False)),
        "strict_score_before": decision.get("strict_score_before"),
        "strict_score_after": decision.get("strict_score_after"),
        "hidden_style_before": decision.get("hidden_style_before"),
        "hidden_style_after": decision.get("hidden_style_after"),
        "direct_http_hits": decision.get("direct_http_hits"),
        "final_submission_format_changed": bool(decision.get("final_submission_format_changed", False)),
        "packaged_strategy_changed": bool(decision.get("packaged_strategy_changed", False)),
        "official_overall_score_claim": bool(decision.get("official_overall_score_claim", False)),
        "source_reports": [
            "outputs/reports/sdk_tool_calling_promotion_preflight.md",
            "outputs/reports/sdk_tool_calling_promotion_plan.md",
            "outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md",
        ],
    }


def _tool_calling_policy_optimizer_status(sources: dict[str, Any]) -> dict[str, Any]:
    optimizer = sources.get("tool_calling_policy_optimizer") or {}
    objectives = sources.get("tool_calling_objective_functions") or {}
    search = sources.get("tool_calling_policy_search_results") or {}
    candidate = sources.get("tool_calling_compiled_policy_candidate") or {}
    decision = sources.get("tool_calling_policy_promotion_decision") or {}
    search_space = optimizer.get("search_space") if isinstance(optimizer.get("search_space"), dict) else {}
    return {
        "optimizer_status": "complete" if optimizer.get("report_type") == "tool_calling_policy_optimizer" else "not_run",
        "objective_status": "complete" if objectives.get("report_type") == "tool_calling_objective_functions" else "not_run",
        "search_status": "complete" if search.get("report_type") == "tool_calling_policy_search_results" else "not_run",
        "compiled_candidate_status": "complete"
        if candidate.get("report_type") == "tool_calling_compiled_policy_candidate"
        else "not_run",
        "promotion_decision_status": "complete"
        if decision.get("report_type") == "tool_calling_policy_promotion_decision"
        else "not_run",
        "decision": decision.get("decision", "not_run"),
        "runtime_change_applied": bool(decision.get("runtime_change_applied", False)),
        "promotion_safe": bool(decision.get("promotion_safe", False)),
        "compiled_policy_id": candidate.get("policy_id"),
        "policy_count": search_space.get("policy_count") or search.get("total_policies_evaluated"),
        "pareto_frontier_count": len(search.get("pareto_frontier_policies") or []),
        "official_overall_score_claim": bool(
            optimizer.get("official_overall_score_claim", decision.get("official_overall_score_claim", False))
        ),
        "diagnostic_only": bool(optimizer.get("diagnostic_only", True)),
        "direct_http_hits": decision.get("direct_http_hits"),
        "final_submission_ready": decision.get("final_submission_ready"),
        "source_reports": [
            "outputs/reports/tool_calling_policy_optimizer.md",
            "outputs/reports/tool_calling_objective_functions.md",
            "outputs/reports/tool_calling_policy_search_results.md",
            "outputs/reports/tool_calling_compiled_policy_candidate.md",
            "outputs/reports/tool_calling_policy_promotion_decision.md",
        ],
    }


def _core_tool_policy_optimizer_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("core_tool_optimization_audit") or {}
    search_space = sources.get("core_tool_optimization_search_space") or {}
    optimizer = sources.get("core_tool_policy_optimizer") or {}
    search = sources.get("core_tool_policy_search_results") or {}
    sql_candidates = sources.get("execute_sql_optimization_candidates") or {}
    api_candidates = sources.get("call_api_optimization_candidates") or {}
    candidate = sources.get("core_tool_compiled_policy_candidate") or {}
    decision = sources.get("core_tool_policy_promotion_decision") or {}
    return {
        "audit_status": "complete" if audit.get("report_type") == "core_tool_optimization_audit" else "not_run",
        "search_space_status": "complete" if search_space.get("report_type") == "core_tool_optimization_search_space" else "not_run",
        "optimizer_status": "complete" if optimizer.get("report_type") == "core_tool_policy_optimizer" else "not_run",
        "search_status": "complete" if search.get("report_type") == "core_tool_policy_search_results" else "not_run",
        "execute_sql_candidate_status": "complete"
        if sql_candidates.get("report_type") == "execute_sql_optimization_candidates"
        else "not_run",
        "call_api_candidate_status": "complete"
        if api_candidates.get("report_type") == "call_api_optimization_candidates"
        else "not_run",
        "compiled_candidate_status": "complete"
        if candidate.get("report_type") == "core_tool_compiled_policy_candidate"
        else "not_run",
        "promotion_decision_status": "complete"
        if decision.get("report_type") == "core_tool_policy_promotion_decision"
        else "not_run",
        "decision": decision.get("decision", "not_run"),
        "compiled_recommendation": candidate.get("recommendation", "not_run"),
        "included_rules": candidate.get("included_rules", []),
        "policy_count": search_space.get("policy_count") or optimizer.get("policy_count"),
        "pareto_frontier_count": search.get("pareto_frontier_count"),
        "runtime_change_expected_in_repo": bool(decision.get("runtime_change_expected_in_repo", False)),
        "runtime_change_applied_by_script": bool(decision.get("runtime_change_applied_by_script", False)),
        "strict_score_before": decision.get("strict_score_before"),
        "strict_score_after_projected": decision.get("strict_score_after_projected"),
        "tool_calls_delta_projected": decision.get("tool_calls_delta_projected"),
        "tokens_delta_projected": decision.get("tokens_delta_projected"),
        "wall_time_delta_projected": decision.get("wall_time_delta_projected"),
        "direct_http_hits": decision.get("direct_http_hits"),
        "final_submission_format_changed": bool(decision.get("final_submission_format_changed", False)),
        "official_overall_score_claim": bool(
            audit.get("official_organizer_weighted_score_claim", decision.get("official_organizer_weighted_score_claim", False))
        ),
        "source_reports": [
            "outputs/reports/core_tool_optimization_audit.md",
            "outputs/reports/core_tool_optimization_search_space.md",
            "outputs/reports/core_tool_policy_optimizer.md",
            "outputs/reports/core_tool_policy_search_results.md",
            "outputs/reports/execute_sql_optimization_candidates.md",
            "outputs/reports/call_api_optimization_candidates.md",
            "outputs/reports/core_tool_compiled_policy_candidate.md",
            "outputs/reports/core_tool_policy_promotion_decision.md",
        ],
    }


def _dashsys_project_skill_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("dashsys_project_skill_audit") or {}
    return {
        "overall_status": audit.get("overall_status", "unavailable"),
        "skill_dir": audit.get("skill_dir", "skills/dashsys_project_skill"),
        "runtime_behavior_changed": audit.get("runtime_behavior_changed", False),
        "credentials_accessed": audit.get("credentials_accessed", False),
        "env_local_accessed": audit.get("env_local_accessed", False),
        "unsafe_live_eval_allowed": audit.get("unsafe_live_eval_allowed", False),
        "mutating_adobe_calls_allowed": audit.get("mutating_adobe_calls_allowed", False),
        "failed_checks": audit.get("failed_checks", []),
        "source_reports": ["outputs/reports/dashsys_project_skill_audit.md"],
    }


def _repo_cleanup_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("repo_cleanup_preflight") or {}
    inventory = sources.get("repo_cleanup_candidate_inventory") or {}
    plan = sources.get("repo_cleanup_deletion_plan") or {}
    result = sources.get("repo_cleanup_result") or {}
    return {
        "status": result.get("status", "not_run"),
        "preflight_status": "complete" if preflight.get("report_type") == "repo_cleanup_preflight" else "not_run",
        "inventory_status": "complete"
        if inventory.get("report_type") == "repo_cleanup_candidate_inventory"
        else "not_run",
        "deletion_plan_status": "complete" if plan.get("report_type") == "repo_cleanup_deletion_plan" else "not_run",
        "deleted_path_count": len(result.get("paths_deleted", [])),
        "size_reduction_bytes": result.get("total_size_reduction_bytes"),
        "manual_review_count": len(result.get("manual_review_paths", [])),
        "runtime_behavior_changed": bool(result.get("runtime_behavior_changed", False)),
        "final_submission_ready_after_cleanup": result.get("final_submission_ready_after_cleanup"),
        "pytest_result": result.get("pytest_result"),
        "source_reports": [
            "outputs/reports/repo_cleanup_preflight.md",
            "outputs/reports/repo_cleanup_candidate_inventory.md",
            "outputs/reports/repo_cleanup_deletion_plan.md",
            "outputs/reports/repo_cleanup_result.md",
        ],
    }


def _context7_audit_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("context7_docs_audit_preflight") or {}
    docs = sources.get("context7_dependency_docs_summary") or {}
    audit = sources.get("context7_code_alignment_audit") or {}
    fix = sources.get("context7_fix_decision") or {}
    return {
        "status": audit.get("status", "not_run"),
        "preflight_status": "complete" if preflight.get("report_type") == "context7_docs_audit_preflight" else "not_run",
        "dependency_docs_status": "complete" if docs.get("report_type") == "context7_dependency_docs_summary" else "not_run",
        "dependency_count": docs.get("dependency_count", 0),
        "context7_found_count": docs.get("context7_found_count", 0),
        "potential_bug_count": (audit.get("summary") or {}).get("potential_bug_count", "not_run"),
        "needs_manual_review_count": (audit.get("summary") or {}).get("needs_manual_review_count", "not_run"),
        "blocked_by_adobe_permission_count": (audit.get("summary") or {}).get(
            "blocked_by_adobe_permission_count", "not_run"
        ),
        "code_changes_applied": bool(fix.get("code_changes_applied", False)),
        "no_context7_backed_code_change": bool(fix.get("no_context7_backed_code_change", True)),
        "packaged_runtime_affected": False,
        "source_reports": [
            "outputs/reports/context7_docs_audit_preflight.md",
            "outputs/reports/context7_dependency_docs_summary.md",
            "outputs/reports/context7_code_alignment_audit.md",
            "outputs/reports/context7_fix_decision.md",
        ],
    }


def _post_live_robustness_status(sources: dict[str, Any]) -> dict[str, Any]:
    preflight = sources.get("post_live_robustness_preflight") or {}
    arbitration = sources.get("live_api_arbitration_regression_guard") or {}
    generated = sources.get("full_generated_prompt_suite_diagnostic") or {}
    nl_sql = sources.get("nl_sql_robustness_audit") or {}
    paraphrase = sources.get("nl_sql_paraphrase_consistency") or {}
    schema_feedback = sources.get("schema_aware_sql_feedback_loop") or {}
    llm_trace = sources.get("llm_agent_trace_decomposition") or {}
    controller = sources.get("controller_rewrite_policy_trial") or {}
    multi_llm = sources.get("multi_llm_backend_robustness") or {}
    tool_efficiency = sources.get("live_tool_efficiency_audit") or {}
    gate = sources.get("integrated_robustness_gate") or {}
    strict = _sql_first_metrics(sources)
    nl_metrics = nl_sql.get("metrics") or {}
    paraphrase_summary = paraphrase.get("summary") or {}
    schema_decision = schema_feedback.get("promotion_decision") or {}
    llm_summary = llm_trace.get("summary") or {}
    return {
        "recommendation": gate.get("recommendation", "not_run"),
        "promotion_allowed": gate.get("promotion_allowed", False),
        "current_strict_score": _first_number(strict.get("avg_final_score"), preflight.get("current_score")),
        "previous_baseline_score": preflight.get("previous_baseline_score"),
        "initial_live_regression_score": preflight.get("initial_live_regression_score"),
        "arbitration_policy": arbitration.get("policy_under_test", "unavailable"),
        "arbitration_policy_safe": arbitration.get("policy_safe_to_keep", "unavailable"),
        "arbitration_critical_violations": arbitration.get("critical_policy_violation_count", "unavailable"),
        "arbitration_warning_count": arbitration.get("policy_warning_count", "unavailable"),
        "generated_prompts_total": generated.get("total_prompts"),
        "generated_prompts_executed": generated.get("executed_prompts"),
        "generated_prompt_runtime_pass_count": generated.get("runtime_pass_count"),
        "generated_prompt_validation_fail_count": generated.get("validation_fail_count"),
        "generated_prompt_unsupported_claim_count": generated.get("unsupported_claim_count"),
        "generated_prompt_live_api_calls": generated.get("live_api_calls"),
        "generated_prompt_template_hit_rate": generated.get("template_hit_rate"),
        "generated_prompt_template_miss_rate": generated.get("template_miss_rate"),
        "template_dependency_score": nl_metrics.get("template_dependency_score"),
        "template_hit_rate": nl_metrics.get("template_hit_rate"),
        "template_miss_rate": nl_metrics.get("template_miss_rate"),
        "paraphrase_consistency_score": (
            paraphrase_summary.get("paraphrase_consistency_score")
            or nl_metrics.get("paraphrase_consistency_score")
        ),
        "schema_aware_decision": schema_decision.get("decision", "not_run"),
        "schema_aware_promotion_allowed": schema_decision.get("promotion_allowed", False),
        "llm_trace_instrumentation_gap_count": llm_summary.get("instrumentation_gap_count"),
        "llm_trace_controller_unpromoted": llm_summary.get("controller_remains_unpromoted"),
        "controller_rewrite_recommendation": controller.get("recommendation", "not_run"),
        "multi_llm_calls_executed": multi_llm.get("llm_calls_executed", "unavailable"),
        "tool_efficiency_recommendation": tool_efficiency.get("recommendation", "not_run"),
        "avg_tool_call_count": _first_number(
            (tool_efficiency.get("live_mode") or {}).get("avg_tool_call_count"),
            strict.get("avg_tool_call_count"),
        ),
        "source_reports": [
            "outputs/reports/post_live_robustness_preflight.md",
            "outputs/reports/live_api_arbitration_regression_guard.md",
            "outputs/reports/full_generated_prompt_suite_diagnostic.md",
            "outputs/reports/nl_sql_robustness_audit.md",
            "outputs/reports/nl_sql_paraphrase_consistency.md",
            "outputs/reports/schema_aware_sql_failure_decomposition.md",
            "outputs/reports/schema_aware_sql_feedback_loop.md",
            "outputs/reports/llm_agent_trace_decomposition.md",
            "outputs/reports/controller_rewrite_policy_trial.md",
            "outputs/reports/multi_llm_backend_robustness.md",
            "outputs/reports/live_tool_efficiency_audit.md",
            "outputs/reports/integrated_robustness_gate.md",
        ],
    }


def _live_api_readiness_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("live_adobe_api_readiness") or {}
    matrix = sources.get("api_required_readiness_matrix") or {}
    smoke = sources.get("live_api_smoke") or {}
    path_diagnosis = sources.get("live_api_endpoint_path_diagnosis") or {}
    blockers = sources.get("live_api_external_blockers") or {}
    followup = sources.get("live_api_endpoint_followup_commands") or {}
    full_run_blocker = sources.get("live_api_full_run_blocker") or {}
    post_permission = sources.get("post_permission_live_api_verification") or {}
    waiting = sources.get("adobe_access_waiting_status") or {}
    safe_get = sources.get("live_api_safe_get_endpoint_matrix") or {}
    endpoint_resolution = sources.get("live_api_remaining_endpoint_resolution") or {}
    guarded_e2e = sources.get("guarded_dash_agent_live_e2e_trial") or {}
    go_no_go = sources.get("live_api_post_exact_go_no_go") or {}
    pipeline = sources.get("live_api_pipeline_trial") or {}
    mock_pipeline = sources.get("mock_live_api_pipeline_trial") or {}
    resolution_after_totals = endpoint_resolution.get("after_totals") or {}
    safe_get_totals = safe_get.get("outcome_counts") or {}
    return {
        "overall_status": audit.get("overall_status", "not_run"),
        "critical_failures": len(audit.get("critical_failures", [])),
        "warnings": len(audit.get("warnings", [])),
        "api_required_readiness_matrix_status": "complete" if matrix.get("report_type") == "api_required_readiness_matrix" else "not_run",
        "api_required_or_api_only_queries": (matrix.get("summary") or {}).get("total_api_required_or_api_only_queries"),
        "smoke_status": smoke.get("status", "not_run"),
        "endpoint_path_diagnosis_status": "complete" if path_diagnosis.get("report_type") == "live_api_endpoint_path_diagnosis" else "not_run",
        "external_blockers_status": "complete" if blockers.get("report_type") == "live_api_external_blockers" else "not_run",
        "followup_commands_status": "complete" if followup.get("report_type") == "live_api_endpoint_followup_commands" else "not_run",
        "full_run_blocker_status": "complete" if full_run_blocker.get("report_type") == "live_api_full_run_blocker" else "not_run",
        "post_permission_verification_status": "complete" if post_permission.get("report_type") == "post_permission_live_api_verification" else "not_run",
        "adobe_access_waiting_status": "complete" if waiting.get("report_type") == "adobe_access_waiting_status" else "not_run",
        "full_live_eval_blocked": blockers.get("full_live_eval_blocked", "unavailable"),
        "full_generated_prompt_suite_blocked": blockers.get("full_generated_prompt_suite_blocked", "unavailable"),
        "safe_get_matrix_status": "complete" if safe_get.get("report_type") == "live_api_safe_get_endpoint_matrix" else "not_run",
        "safe_get_total_attempted": resolution_after_totals.get("total_safe_get_endpoints_attempted", smoke.get("endpoints_attempted")),
        "safe_get_live_success_count": resolution_after_totals.get("live_success_count", safe_get_totals.get("live_success")),
        "safe_get_live_empty_count": resolution_after_totals.get("live_empty_count", safe_get_totals.get("live_empty")),
        "endpoint_path_failures_remaining": resolution_after_totals.get("endpoint_path_issue_count", "unavailable"),
        "runtime_relevant_endpoint_path_failures_remain": endpoint_resolution.get("runtime_relevant_endpoint_path_failures_remain", "unavailable"),
        "remaining_endpoint_resolution_status": "complete" if endpoint_resolution.get("report_type") == "live_api_remaining_endpoint_resolution_summary" else "not_run",
        "guarded_live_e2e_status": guarded_e2e.get("status", "not_run"),
        "guarded_live_e2e_parser_evidencebus_failure_count": (guarded_e2e.get("summary") or {}).get("parser_evidencebus_failure_count"),
        "guarded_live_e2e_unsupported_api_claim_count": (guarded_e2e.get("summary") or {}).get("unsupported_api_claim_count"),
        "guarded_live_e2e_unresolved_path_failure_count": (guarded_e2e.get("summary") or {}).get("unresolved_path_failure_count"),
        "go_no_go_recommendation": go_no_go.get("go_no_go_recommendation", "unavailable"),
        "pipeline_trial_status": pipeline.get("status", "not_run"),
        "mock_pipeline_trial_status": mock_pipeline.get("status", "not_run"),
        "mock_parser_success_count": mock_pipeline.get("parser_success_count", "not_run"),
        "mock_discovery_chain_simulated_count": mock_pipeline.get("discovery_chain_simulated_count", "not_run"),
        "credentials_present": smoke.get("credentials_present", False),
        "live_mode_attempted": bool(smoke.get("live_mode_attempted") or pipeline.get("live_mode_attempted")),
        "dry_run_fallback_verified": bool(smoke.get("dry_run_fallback_verified") or pipeline.get("dry_run_fallback_verified")),
        "infrastructure_validation_only": True,
        "official_score_claim": False,
        "packaged_runtime_affected": False,
        "next_best_candidate": "Live Adobe API response parser + discovery-chain readiness + EvidenceBus API evidence pipeline",
        "source_reports": [
            "outputs/reports/live_adobe_api_readiness_audit.md",
            "outputs/reports/api_required_readiness_matrix.md",
            "outputs/reports/live_api_readiness_smoke.md",
            "outputs/reports/live_api_endpoint_path_diagnosis.md",
            "outputs/reports/live_api_external_blockers.md",
            "outputs/reports/live_api_endpoint_followup_commands.md",
            "outputs/reports/live_api_full_run_blocker.md",
            "outputs/reports/post_permission_live_api_verification.md",
            "outputs/reports/adobe_access_waiting_status.md",
            "outputs/reports/live_api_safe_get_endpoint_matrix.md",
            "outputs/reports/live_api_remaining_endpoint_resolution_summary.md",
            "outputs/reports/guarded_dash_agent_live_e2e_trial.md",
            "outputs/reports/live_api_post_exact_reproduction_go_no_go.md",
            "outputs/reports/live_api_evidence_pipeline_trial.md",
            "outputs/reports/mock_live_api_evidence_pipeline_trial.md",
        ],
    }


def _evidence_answer_status(sources: dict[str, Any]) -> dict[str, Any]:
    audit = sources.get("evidence_usage_audit") or {}
    trial = sources.get("evidence_aware_answer_rewrite_trial") or {}
    final = sources.get("feedback_loop_answer_synthesis_final") or {}
    sql_audit = sources.get("sql_evidence_usage_audit") or {}
    confidence = sources.get("confidence_calibration_audit") or {}
    token = sources.get("token_efficiency_audit") or {}
    summary = trial.get("summary") or {}
    recommendation = final.get("final_recommendation") or summary.get("recommendation") or "not_run"
    return {
        "audit_status": audit.get("status", "not_run"),
        "trial_status": trial.get("status", "not_run"),
        "sql_audit_status": sql_audit.get("status", "not_run"),
        "confidence_audit_status": confidence.get("status", "not_run"),
        "token_audit_status": token.get("status", "not_run"),
        "rows_audited": audit.get("total_rows", 0),
        "rows_rewritten": summary.get("rows_rewritten", 0),
        "rows_rejected": summary.get("rows_rejected", 0),
        "best_variant": summary.get("best_variant") or final.get("best_variant"),
        "best_strict_score_delta": summary.get("best_strict_score_delta") or final.get("best_strict_score_delta"),
        "recommendation": recommendation,
        "answer_only_invariant_enforced": True,
        "packaged_runtime_changed": False,
        "official_score_claim": False,
        "source_reports": [
            "outputs/reports/evidence_usage_audit.md",
            "outputs/reports/evidence_aware_answer_rewrite_trial.md",
            "outputs/reports/feedback_loop_answer_synthesis_final.md",
            "outputs/reports/sql_evidence_usage_audit.md",
            "outputs/reports/confidence_calibration_audit.md",
            "outputs/reports/token_efficiency_audit.md",
        ],
    }


def _first_number(*values: Any) -> float | str:
    for value in values:
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return "unavailable"


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(payload)
    return safe if isinstance(safe, dict) else payload


def _rel(config: Config, path: Path) -> str:
    return path.resolve().relative_to(config.project_root.resolve()).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
