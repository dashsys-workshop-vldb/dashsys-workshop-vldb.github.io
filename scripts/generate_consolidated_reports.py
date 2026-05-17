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
        "live_api_pipeline_trial": _load_json(outputs / "reports" / "live_api_evidence_pipeline_trial.json"),
        "mock_live_api_pipeline_trial": _load_json(outputs / "reports" / "mock_live_api_evidence_pipeline_trial.json"),
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
        "llm_semantic_routing_helper": _semantic_router_status(sources),
        "decision_stage_methodology": _decision_stage_status(sources),
        "evidence_aware_answer_synthesis": _evidence_answer_status(sources),
        "score_focused_core_path": _score_path_status(sources),
        "comprehensive_failure_analysis": _comprehensive_failure_status(sources),
        "context7_documentation_grounded_audit": _context7_audit_status(sources),
        "source_reports": [
            "outputs/eval_results_strict.json",
            "outputs/winner_readiness_report.json",
            "outputs/hidden_style_eval.json",
            "outputs/official_token_reduction_promotion_report.json",
            "outputs/reports/post_permission_live_api_verification.md",
            "outputs/reports/adobe_access_waiting_status.md",
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
        "source_reports": [
            "outputs/llm_sdk_backend_check.json",
            "outputs/llm_baseline_eval_report.json",
            "outputs/llm_strict_baseline_eval.json",
            "outputs/llm_hidden_style_diagnostic.json",
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
        "source_reports": [
            "outputs/autonomous_score_push_report.json",
            "outputs/autonomous_packaged_trial.json",
            "outputs/score075_blocker_analysis.json",
            "outputs/supportable_answer_rewrite_eval.json",
            "outputs/endpoint_family_tiebreak_v2_shadow.json",
            "outputs/ast_guided_sql_candidate_canary.json",
            "outputs/reports/live_adobe_api_readiness_audit.json",
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
            "outputs/reports/overnight_autonomous_improvement_report.md",
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
                "label": "Full 250-prompt generated suite diagnostic only; no official strict score claim.",
            },
            {
                "path": "outputs/reports/generated_prompt_coverage_gap_analysis.md",
                "label": "Generated prompt coverage gaps; diagnostic-only and not promotion evidence.",
            },
        ],
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
            "evidence_aware_answer_synthesis": system["evidence_aware_answer_synthesis"].get("recommendation"),
            "llm_recommendation": llm["recommendation"],
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
            f"- Post-permission live verification: `{payload['live_adobe_api_readiness'].get('post_permission_verification_status')}`; "
            f"waiting-status report: `{payload['live_adobe_api_readiness'].get('adobe_access_waiting_status')}`",
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
    pipeline = sources.get("live_api_pipeline_trial") or {}
    mock_pipeline = sources.get("mock_live_api_pipeline_trial") or {}
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
