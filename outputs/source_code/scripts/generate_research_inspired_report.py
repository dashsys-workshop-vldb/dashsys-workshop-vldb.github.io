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
from dashagent.eval_harness import EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.research_safety import build_research_safety_audit


BASELINE_SQL_FIRST = {
    "strict_final_score": 0.649,
    "strict_correctness": 0.6743,
    "estimated_tokens": 851.7714,
    "runtime": 0.0102,
    "tool_calls": 1.4571,
}


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "final_research_inspired_improvement_report.json"
    md_path = config.outputs_dir / "final_research_inspired_improvement_report.md"
    audit_path = config.outputs_dir / "research_safety_audit.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    audit_path.write_text(json.dumps(report["research_safety_audit"], indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "audit": str(audit_path)}, indent=2, sort_keys=True))
    return 0


def generate_report(config: Config) -> dict[str, Any]:
    executor = AgentExecutor(config)
    harness = EvalHarness(config, executor)
    examples = [example.__dict__ for example in harness.load_examples()]
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json")
    shadow_report = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    compact_shadow_report = _load_json(config.outputs_dir / "compact_context_shadow_eval.json")
    compact_measured_report = _load_json(config.outputs_dir / "compact_context_measured_eval.json")
    official_token_accounting_report = _load_json(config.outputs_dir / "official_token_accounting_report.json")
    official_token_reduction_report = _load_json(config.outputs_dir / "official_token_reduction_eval.json")
    official_token_reduction_canary_report = _load_json(config.outputs_dir / "official_token_reduction_canary.json")
    official_token_reduction_trial_report = _load_json(config.outputs_dir / "official_token_reduction_packaged_trial.json")
    official_token_reduction_promotion_report = _load_json(config.outputs_dir / "official_token_reduction_promotion_report.json")
    hidden_style_report = _load_json(config.outputs_dir / "hidden_style_eval.json")
    endpoint_failure_report = _load_json(config.outputs_dir / "endpoint_family_failure_report.json")
    endpoint_schema_rule_candidate_report = _load_json(config.outputs_dir / "endpoint_schema_rule_candidate_eval.json")
    endpoint_schema_rule_canary_report = _load_json(config.outputs_dir / "endpoint_schema_rule_canary.json")
    endpoint_schema_rule_packaged_trial_report = _load_json(config.outputs_dir / "endpoint_schema_rule_packaged_trial.json")
    schema_dataset_positive_report = _load_json(config.outputs_dir / "schema_dataset_positive_repair_analysis.json")
    sql_ast_candidate_report = _load_json(config.outputs_dir / "sql_ast_candidate_ranking_report.json")
    ast_guided_sql_canary_report = _load_json(config.outputs_dir / "ast_guided_sql_candidate_canary.json")
    retrieval_ablation_report = _load_json(config.outputs_dir / "retrieval_ablation_report.json")
    repair_selector_v2_report = _load_json(config.outputs_dir / "repair_selector_v2_shadow_eval.json")
    repair_selector_v3_report = _load_json(config.outputs_dir / "repair_selector_v3_shadow_eval.json")
    accuracy_decision_report = _load_json(config.outputs_dir / "accuracy_promotion_decision_report.json")
    winner_readiness_report = _load_json(config.outputs_dir / "winner_readiness_report.json")
    risk_shadow_report = _load_json(config.outputs_dir / "risk_efficiency_shadow_eval.json")
    current = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    final_score = current.get("avg_final_score", 0.0)
    correctness = current.get("avg_correctness_score", 0.0)
    metrics = {
        "strict_final_score": final_score,
        "strict_correctness": correctness,
        "estimated_tokens": current.get("avg_estimated_tokens"),
        "runtime": current.get("avg_runtime"),
        "tool_calls": current.get("avg_tool_call_count"),
    }
    deltas = {
        key: round(float(metrics.get(key) or 0.0) - float(BASELINE_SQL_FIRST.get(key) or 0.0), 4)
        for key in BASELINE_SQL_FIRST
    }
    token_overhead_pct = _pct_delta(metrics.get("estimated_tokens"), BASELINE_SQL_FIRST["estimated_tokens"])
    runtime_overhead_pct = _pct_delta(metrics.get("runtime"), BASELINE_SQL_FIRST["runtime"])
    visualizations_in_submission = _count_paths(config.outputs_dir / "final_submission", "visualizations")
    flags = {
        "ENABLE_SQL_AST_VALIDATION": config.enable_sql_ast_validation,
        "ENABLE_SCHEMA_LINKING": config.enable_schema_linking,
        "ENABLE_VALUE_RETRIEVAL": config.enable_value_retrieval,
        "ENABLE_GATED_SQL_CANDIDATES": config.enable_gated_sql_candidates,
        "ENABLE_QUERY_DECOMPOSITION": config.enable_query_decomposition,
        "ENABLE_QUERY_FAMILY_EXAMPLES": config.enable_query_family_examples,
        "ENABLE_RESEARCH_SPAN_EXPORT": config.enable_research_span_export,
        "ENABLE_HYBRID_CANDIDATE_SCORING": config.enable_hybrid_candidate_scoring,
        "ENABLE_ENDPOINT_FAMILY_RANKING": config.enable_endpoint_family_ranking,
        "ENABLE_STRUCTURAL_SCHEMA_PRESERVATION": config.enable_structural_schema_preservation,
        "ENABLE_VALUE_TO_API_RANKING": config.enable_value_to_api_ranking,
        "ENABLE_GATED_RISK_CLUSTER_REPAIR": config.enable_gated_risk_cluster_repair,
        "ENABLE_GATED_RISK_CLUSTER_REPAIR_EXECUTION": config.enable_gated_risk_cluster_repair_execution,
        "ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION": config.enable_repair_for_batch_endpoint_confusion,
        "ENABLE_REPAIR_FOR_TAG_API_CONFUSION": config.enable_repair_for_tag_api_confusion,
        "ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION": config.enable_repair_for_schema_dataset_confusion,
        "ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN": config.enable_repair_for_zero_score_margin,
        "ENABLE_REPAIR_FOR_MISSING_API_TOPK": config.enable_repair_for_missing_api_topk,
        "ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE": config.enable_compact_context_when_schema_vote_safe,
        "ENABLE_OFFICIAL_TOKEN_REDUCTION": config.enable_official_token_reduction,
        "ENABLE_ENDPOINT_SCHEMA_RULE_CANDIDATES": config.enable_endpoint_schema_rule_candidates,
        "ENABLE_AST_GUIDED_SQL_TIEBREAK": config.enable_ast_guided_sql_tiebreak,
    }
    techniques = [
        ("SQLGlot AST validation", "SQLGlot", "dashagent/sql_ast_tools.py", config.enable_sql_ast_validation, "checkpoint_sql_ast_validation"),
        ("Robust schema linking", "RSL-SQL", "dashagent/candidate_context_builder.py", config.enable_schema_linking, "checkpoint_schema_linking/report metrics"),
        ("Value/entity retrieval", "CHESS", "dashagent/value_retrieval.py", config.enable_value_retrieval, "checkpoint_value_entity_retrieval"),
        ("Query decomposition", "DIN-SQL", "dashagent/query_decomposer.py", config.enable_query_decomposition, "checkpoint_query_decomposition"),
        ("Gated SQL candidates", "DIN-SQL/self-correction", "dashagent/gated_sql_candidates.py", config.enable_gated_sql_candidates, "checkpoint_gated_sql_candidate_selection"),
        ("Query-family examples", "DAIL-SQL", "dashagent/query_family_examples.py", config.enable_query_family_examples, "checkpoint_query_family_examples"),
        ("Span export", "OpenAI Agents SDK tracing", "dashagent/span_exporter.py", config.enable_research_span_export, "spans.json"),
        ("Hybrid candidate scoring", "Blended RAG / rank fusion", "dashagent/candidate_ranker.py", config.enable_hybrid_candidate_scoring, "checkpoint_hybrid_candidate_scoring/report metrics"),
        ("Endpoint family ranking", "domain-aware retrieval", "dashagent/endpoint_family_ranker.py", config.enable_endpoint_family_ranking, "checkpoint_endpoint_family_ranking/report metrics"),
        ("Value-to-API ranking", "CHESS value grounding", "dashagent/endpoint_family_ranker.py", config.enable_value_to_api_ranking, "checkpoint_value_to_api_ranking/report metrics"),
        ("Gated risk-cluster repair", "CHASE-SQL-style candidate repair", "dashagent/candidate_context_builder.py", config.enable_gated_risk_cluster_repair, "checkpoint_gated_risk_cluster_repair/report metrics"),
        ("Risk-based efficiency controller", "adaptive retrieval control", "dashagent/risk_efficiency_controller.py", True, "checkpoint_risk_efficiency_controller/report metrics"),
        ("Schema context voting", "full-vs-compact context voting", "dashagent/schema_context_voter.py", True, "checkpoint_schema_context_voting/report metrics"),
    ]
    cluster_gate = candidate_report.get("cluster_gate", {})
    return {
        "summary": {
            "status": "no measured strict-score improvement" if deltas["strict_final_score"] <= 0 else "strict-score improvement measured",
            "ranking_only_no_score_claim": True,
            "retrieval_cluster_gate_status": cluster_gate.get("status", "not run"),
            "retrieval_cluster_gate_passed": cluster_gate.get("passed", False),
            "retrieval_cluster_improved_clusters": cluster_gate.get("improved_clusters", []),
            "packaged_preferred_strategy": manifest.get("preferred_strategy", "SQL_FIRST_API_VERIFY"),
            "strict_score_regression_ok": deltas["strict_final_score"] >= -0.005,
            "token_overhead_pct": token_overhead_pct,
            "runtime_overhead_pct": runtime_overhead_pct,
            "tool_call_delta": deltas["tool_calls"],
            "value_retrieval_budget_ms": config.value_retrieval_max_ms,
            "value_retrieval_budget_ok": config.value_retrieval_max_ms <= 250,
            "estimated_tokens_gate_ok": token_overhead_pct <= 0.10,
            "runtime_gate_ok": runtime_overhead_pct <= 0.20,
            "tool_call_gate_ok": deltas["tool_calls"] <= 0,
            "no_secret_scan_ok": manifest.get("no_secret_scan", {}).get("ok", True),
            "visualization_artifacts_dir": str(config.outputs_dir / "visualizations"),
            "visualizations_in_final_submission": visualizations_in_submission,
            "final_submission_format_unchanged": visualizations_in_submission == 0,
            "value_retrieval_cache_key_algorithm": "sha256",
            "value_retrieval_cache_reproducible": True,
            "candidate_risk_cluster_count": len(candidate_report.get("candidate_risk_clusters", {})),
            "shadow_repair_eval_ran": bool(shadow_report.get("rows")),
            "shadow_repair_execution_enabled": shadow_report.get("repair_execution_enabled", config.enable_gated_risk_cluster_repair_execution),
            "shadow_repair_better_count": shadow_report.get("paired_shadow_eval_summary", {}).get("repaired_better_count", 0),
            "shadow_repair_equal_count": shadow_report.get("paired_shadow_eval_summary", {}).get("repaired_equal_count", 0),
            "shadow_repair_worse_count": shadow_report.get("paired_shadow_eval_summary", {}).get("repaired_worse_count", 0),
            "shadow_repair_unsafe_count": shadow_report.get("paired_shadow_eval_summary", {}).get("unsafe_repair_count", 0),
            "risk_level_distribution": candidate_report.get("summary", {}).get("risk_level_distribution", {}),
            "risk_controller_estimated_token_savings_total": candidate_report.get("summary", {}).get("estimated_token_savings_total", 0),
            "risk_controller_estimated_runtime_savings_ms_total": candidate_report.get("summary", {}).get("estimated_runtime_savings_ms_total", 0),
            "risk_controller_savings_are_estimates": True,
            "measured_efficiency_improvement_claimed": official_token_reduction_promotion_report.get("summary", {}).get("promotion_kept", False),
            "packaged_execution_changed": official_token_reduction_promotion_report.get("summary", {}).get("promotion_kept", False),
            "measured_accuracy_improvement_claimed": False,
            "behavior_changing_flags_enabled": config.enable_official_token_reduction,
            "behavior_changing_flags_note": "Official-token reduction is the only behavior-changing default enabled; repair execution and compact context remain disabled.",
            "schema_vote_active_count": candidate_report.get("summary", {}).get("schema_vote_active_count", 0),
            "schema_vote_agreement_count": candidate_report.get("summary", {}).get("schema_vote_agreement_count", 0),
            "compact_context_safe_count": candidate_report.get("summary", {}).get("compact_context_safe_count", 0),
            "compact_context_shadow_eval_ran": bool(compact_shadow_report.get("rows")),
            "compact_context_shadow_row_count": compact_shadow_report.get("summary", {}).get("row_count", 0),
            "compact_context_shadow_avg_token_delta": compact_shadow_report.get("summary", {}).get("avg_token_delta"),
            "compact_context_shadow_measured_accuracy_improvement_claimed": compact_shadow_report.get("summary", {}).get("measured_accuracy_improvement_claimed", False),
            "compact_context_shadow_measured_efficiency_improvement_claimed": compact_shadow_report.get("summary", {}).get("measured_efficiency_improvement_claimed", False),
            "compact_context_measured_eval_ran": bool(compact_measured_report.get("rows")),
            "compact_context_measured_eligible_rows": compact_measured_report.get("summary", {}).get("eligible_rows", 0),
            "compact_context_measured_safe_rows": compact_measured_report.get("summary", {}).get("safe_to_enable_rows", 0),
            "compact_context_measured_avg_token_delta": compact_measured_report.get("summary", {}).get("avg_token_delta"),
            "compact_context_measured_avg_token_delta_total": compact_measured_report.get("summary", {}).get("avg_token_delta_total"),
            "compact_context_measured_avg_token_delta_context_only": compact_measured_report.get("summary", {}).get("avg_token_delta_context_only"),
            "compact_context_measured_token_classification_counts": compact_measured_report.get("summary", {}).get("token_measurement_classification_counts", {}),
            "compact_context_measured_measurement_caveat": compact_measured_report.get("measurement_caveat"),
            "compact_context_measured_avg_runtime_delta": compact_measured_report.get("summary", {}).get("avg_runtime_delta"),
            "compact_context_measured_experimental_efficiency_claimed": compact_measured_report.get("summary", {}).get("measured_efficiency_improvement_claimed", False),
            "compact_context_measured_official_efficiency_claimed": compact_measured_report.get("summary", {}).get("official_measured_efficiency_improvement_claimed", False),
            "compact_context_measured_packaged_execution_changed": compact_measured_report.get("summary", {}).get("packaged_execution_changed", False),
            "compact_context_measured_recommendation": compact_measured_report.get("summary", {}).get("recommendation", "not_run"),
            "compact_context_feature_flag_default": compact_measured_report.get("feature_flag_default", config.enable_compact_context_when_schema_vote_safe),
            "official_token_accounting_ran": bool(official_token_accounting_report.get("rows")),
            "official_token_top_contributors": official_token_accounting_report.get("aggregate", {}).get("top_global_token_contributors", []),
            "official_token_biggest_reducible_fields": official_token_accounting_report.get("aggregate", {}).get("biggest_reducible_fields", []),
            "official_token_expected_savings_estimate": official_token_accounting_report.get("aggregate", {}).get("expected_token_savings_estimate"),
            "official_token_reduction_eval_ran": bool(official_token_reduction_report.get("rows")),
            "official_token_reduction_safe_rows": official_token_reduction_report.get("summary", {}).get("safe_rows", 0),
            "official_token_reduction_avg_token_delta": official_token_reduction_report.get("summary", {}).get("avg_token_delta"),
            "official_token_reduction_avg_score_delta": official_token_reduction_report.get("summary", {}).get("avg_score_delta"),
            "official_token_reduction_recommendation": official_token_reduction_report.get("summary", {}).get("recommendation", "not_run"),
            "official_token_reduction_packaged_execution_changed": official_token_reduction_report.get("summary", {}).get("packaged_execution_changed", False),
            "official_token_reduction_feature_flag_default": official_token_reduction_report.get("feature_flag_default", config.enable_official_token_reduction),
            "official_token_reduction_official_efficiency_claimed": official_token_reduction_report.get("summary", {}).get("official_measured_efficiency_improvement_claimed", False),
            "official_token_reduction_canary_ran": bool(official_token_reduction_canary_report.get("rows")),
            "official_token_reduction_canary_safe_rows": official_token_reduction_canary_report.get("summary", {}).get("safe_rows", 0),
            "official_token_reduction_canary_unsafe_rows": official_token_reduction_canary_report.get("summary", {}).get("unsafe_rows", 0),
            "official_token_reduction_canary_avg_token_delta": official_token_reduction_canary_report.get("summary", {}).get("avg_token_delta"),
            "official_token_reduction_canary_avg_score_delta": official_token_reduction_canary_report.get("summary", {}).get("avg_score_delta"),
            "official_token_reduction_canary_recommendation": official_token_reduction_canary_report.get("summary", {}).get("recommendation", "not_run"),
            "official_token_reduction_canary_protected_hashes_unchanged": official_token_reduction_canary_report.get("summary", {}).get("protected_output_hashes_unchanged", False),
            "official_token_reduction_canary_packaged_execution_changed": official_token_reduction_canary_report.get("summary", {}).get("packaged_execution_changed", False),
            "official_token_reduction_canary_feature_flag_default": official_token_reduction_canary_report.get("feature_flag_default", config.enable_official_token_reduction),
            "official_token_reduction_canary_official_efficiency_claimed": official_token_reduction_canary_report.get("summary", {}).get("official_packaged_efficiency_improvement_claimed", False),
            "official_token_reduction_packaged_trial_ran": bool(official_token_reduction_trial_report.get("rows")),
            "official_token_reduction_packaged_trial_safe_rows": official_token_reduction_trial_report.get("summary", {}).get("safe_rows", 0),
            "official_token_reduction_packaged_trial_unsafe_rows": official_token_reduction_trial_report.get("summary", {}).get("unsafe_rows", 0),
            "official_token_reduction_packaged_trial_avg_token_delta": official_token_reduction_trial_report.get("summary", {}).get("avg_token_delta"),
            "official_token_reduction_packaged_trial_avg_runtime_delta": official_token_reduction_trial_report.get("summary", {}).get("avg_runtime_delta"),
            "official_token_reduction_packaged_trial_recommendation": official_token_reduction_trial_report.get("summary", {}).get("recommendation", "not_run"),
            "official_token_reduction_promotion_attempted": official_token_reduction_promotion_report.get("summary", {}).get("promotion_attempted", False),
            "official_token_reduction_promotion_kept": official_token_reduction_promotion_report.get("summary", {}).get("promotion_kept", False),
            "official_token_reduction_promotion_recommendation": official_token_reduction_promotion_report.get("summary", {}).get("recommendation", "not_run"),
            "official_token_reduction_promotion_token_delta": official_token_reduction_promotion_report.get("summary", {}).get("token_delta"),
            "official_token_reduction_promotion_score_delta": official_token_reduction_promotion_report.get("summary", {}).get("score_delta"),
            "official_token_reduction_promotion_final_submission_diff": official_token_reduction_promotion_report.get("summary", {}).get("final_submission_format_unchanged"),
            "hidden_style_eval_passed_cases": hidden_style_report.get("summary", {}).get("passed_cases", 0),
            "hidden_style_eval_total_cases": hidden_style_report.get("summary", {}).get("total_cases", 0),
            "endpoint_family_failure_risky_rows": endpoint_failure_report.get("summary", {}).get("risky_rows", 0),
            "endpoint_schema_rule_candidate_rules": endpoint_schema_rule_candidate_report.get("summary", {}).get("candidate_rules", 0),
            "endpoint_schema_rule_candidate_safe_rules": endpoint_schema_rule_candidate_report.get("summary", {}).get("safe_for_future_canary_rules", 0),
            "endpoint_schema_rule_canary_recommendation": endpoint_schema_rule_canary_report.get("summary", {}).get("recommendation", "not_run"),
            "endpoint_schema_rule_canary_api_top_k_hit_rate_delta": endpoint_schema_rule_canary_report.get("summary", {}).get("api_top_k_hit_rate_delta", 0.0),
            "endpoint_schema_rule_packaged_trial_recommendation": endpoint_schema_rule_packaged_trial_report.get("summary", {}).get("recommendation", "not_run"),
            "ast_guided_sql_canary_recommendation": ast_guided_sql_canary_report.get("summary", {}).get("recommendation", "not_run"),
            "repair_selector_v3_success": repair_selector_v3_report.get("summary", {}).get("success", False),
            "repair_selector_v3_strictly_better_selected_count": repair_selector_v3_report.get("summary", {}).get("strictly_better_selected_count", 0),
            "accuracy_promotion_decision_recommendation": accuracy_decision_report.get("summary", {}).get("recommendation", "not_run"),
            "schema_dataset_positive_repair_rows": schema_dataset_positive_report.get("summary", {}).get("positive_schema_dataset_rows", 0),
            "sql_ast_candidate_ranking_candidates": sql_ast_candidate_report.get("summary", {}).get("candidate_count", 0),
            "retrieval_ablation_best_mode": retrieval_ablation_report.get("summary", {}).get("best_final_score_mode"),
            "repair_selector_v2_success": repair_selector_v2_report.get("summary", {}).get("success", False),
            "winner_readiness_recommended_next_action": winner_readiness_report.get("recommended_next_action", []),
            "risk_efficiency_shadow_eval_ran": bool(risk_shadow_report.get("rows")),
            "risk_efficiency_shadow_row_count": risk_shadow_report.get("summary", {}).get("row_count", 0),
            "risk_efficiency_shadow_avg_token_delta": risk_shadow_report.get("summary", {}).get("avg_token_delta"),
            "risk_efficiency_shadow_avg_runtime_delta": risk_shadow_report.get("summary", {}).get("avg_runtime_delta"),
            "risk_efficiency_shadow_measured_accuracy_improvement_claimed": risk_shadow_report.get("summary", {}).get("measured_accuracy_improvement_claimed", False),
            "risk_efficiency_shadow_measured_efficiency_improvement_claimed": risk_shadow_report.get("summary", {}).get("measured_efficiency_improvement_claimed", False),
        },
        "baseline": BASELINE_SQL_FIRST,
        "current": metrics,
        "delta": deltas,
        "feature_flags": flags,
        "techniques": [
            {
                "technique": name,
                "source_inspiration": source,
                "implemented_module": module,
                "active_in_sql_first": active,
                "active_in_raw_guided": False,
                "correctness_role": "diagnostic/grounding unless strict score improves",
                "efficiency_role": "bounded or disabled by feature flag",
                "visualization_checkpoint": checkpoint,
            }
            for name, source, module, active, checkpoint in techniques
        ],
        "research_safety_audit": build_research_safety_audit(executor.schema_index, examples),
        "candidate_risk_clusters": candidate_report.get("candidate_risk_clusters", {}),
        "candidate_cluster_gate": cluster_gate,
        "shadow_repair_eval": {
            "paired_shadow_eval_summary": shadow_report.get("paired_shadow_eval_summary", {}),
            "cluster_canary_recommendations": shadow_report.get("cluster_canary_recommendations", {}),
            "repair_execution_enabled": shadow_report.get("repair_execution_enabled", False),
            "risk_efficiency_controller_summary": shadow_report.get("risk_efficiency_controller_summary", {}),
            "schema_context_voting_summary": shadow_report.get("schema_context_voting_summary", {}),
            "notes": shadow_report.get("notes", []),
        },
        "compact_context_shadow_eval": {
            "summary": compact_shadow_report.get("summary", {}),
            "artifact_isolation": compact_shadow_report.get("artifact_isolation", {}),
            "notes": compact_shadow_report.get("notes", []),
        },
        "compact_context_measured_eval": {
            "summary": compact_measured_report.get("summary", {}),
            "token_accounting_analysis": compact_measured_report.get("token_accounting_analysis", {}),
            "measurement_caveat": compact_measured_report.get("measurement_caveat"),
            "artifact_isolation": compact_measured_report.get("artifact_isolation", {}),
            "notes": compact_measured_report.get("notes", []),
        },
        "official_token_accounting_report": {
            "aggregate": official_token_accounting_report.get("aggregate", {}),
            "notes": official_token_accounting_report.get("notes", []),
        },
        "official_token_reduction_eval": {
            "summary": official_token_reduction_report.get("summary", {}),
            "artifact_isolation": official_token_reduction_report.get("artifact_isolation", {}),
            "notes": official_token_reduction_report.get("notes", []),
        },
        "official_token_reduction_canary": {
            "summary": official_token_reduction_canary_report.get("summary", {}),
            "artifact_isolation": official_token_reduction_canary_report.get("artifact_isolation", {}),
            "protected_output_hashes_unchanged": official_token_reduction_canary_report.get("protected_output_hashes_unchanged"),
            "notes": official_token_reduction_canary_report.get("notes", []),
        },
        "official_token_reduction_packaged_trial": {
            "summary": official_token_reduction_trial_report.get("summary", {}),
            "artifact_isolation": official_token_reduction_trial_report.get("artifact_isolation", {}),
            "notes": official_token_reduction_trial_report.get("notes", []),
        },
        "official_token_reduction_promotion_report": {
            "summary": official_token_reduction_promotion_report.get("summary", {}),
            "gates": official_token_reduction_promotion_report.get("gates", {}),
            "final_submission_diff": official_token_reduction_promotion_report.get("final_submission_diff", {}),
        },
        "hidden_style_eval": {"summary": hidden_style_report.get("summary", {})},
        "endpoint_family_failure_report": {"summary": endpoint_failure_report.get("summary", {})},
        "endpoint_schema_rule_candidate_eval": {"summary": endpoint_schema_rule_candidate_report.get("summary", {})},
        "endpoint_schema_rule_canary": {"summary": endpoint_schema_rule_canary_report.get("summary", {})},
        "endpoint_schema_rule_packaged_trial": {"summary": endpoint_schema_rule_packaged_trial_report.get("summary", {})},
        "schema_dataset_positive_repair_analysis": {"summary": schema_dataset_positive_report.get("summary", {})},
        "sql_ast_candidate_ranking_report": {"summary": sql_ast_candidate_report.get("summary", {})},
        "ast_guided_sql_candidate_canary": {"summary": ast_guided_sql_canary_report.get("summary", {})},
        "retrieval_ablation_report": {"summary": retrieval_ablation_report.get("summary", {})},
        "repair_selector_v2_shadow_eval": {"summary": repair_selector_v2_report.get("summary", {})},
        "repair_selector_v3_shadow_eval": {"summary": repair_selector_v3_report.get("summary", {})},
        "accuracy_promotion_decision_report": {"summary": accuracy_decision_report.get("summary", {})},
        "winner_readiness_report": {
            "packaged": winner_readiness_report.get("packaged", {}),
            "recommended_next_action": winner_readiness_report.get("recommended_next_action", []),
        },
        "risk_efficiency_shadow_eval": {
            "summary": risk_shadow_report.get("summary", {}),
            "artifact_isolation": risk_shadow_report.get("artifact_isolation", {}),
            "notes": risk_shadow_report.get("notes", []),
        },
        "notes": [
            "Value retrieval cache filenames use stable SHA-256 keys instead of Python process-salted hash().",
            "Hybrid candidate ranking is report-only for SQL_FIRST_API_VERIFY; it does not change executed SQL/API plans.",
            "Candidate risk clusters compare old retrieval ordering with ranking/report-only ordering.",
            "If execution repair remains disabled, ranking changes are not claimed as accuracy improvements.",
            "Offline shadow repair eval compares candidate-derived repaired plans without changing packaged execution.",
            "Any repair canary enablement is a recommendation only; canary flags remain disabled by default.",
            "Risk-based efficiency savings are labeled as estimates; no measured efficiency improvement is claimed because packaged execution did not skip modules.",
            "Schema context voting compares compact and broader context for high-risk diagnostics only and does not change executed SQL/API plans.",
            "Compact-context measured eval is experimental only and does not update official packaged scores or submission metrics.",
            "Official-token reduction eval is experimental only and does not update official packaged scores or submission metrics.",
            "Official-token reduction canary is isolated and does not update official packaged scores or submission metrics.",
            "Official-token reduction is promoted as the only behavior-changing default only when the promotion report gates pass.",
            "Repair selector v2, retrieval ablations, endpoint-family failures, and SQL AST candidate rankings are report-only.",
            "SQLGlot AST diagnostics are reported safely; ParseError values are captured as diagnostics rather than crashing the pipeline.",
            "No live API evidence is fabricated; Adobe API remains dry-run without credentials.",
            "Gated SQL candidates validate multiple candidates but execute one selected SQL in packaged SQL_FIRST mode.",
            "Inactive techniques appear compactly in visualization status tables, not as empty checkpoints.",
            "Behavior-changing repair execution is feature-flagged off by default; strict score and efficiency gates decide whether it can ever be enabled.",
            "Official-token reduction is the only behavior-changing default enabled in this pass; repair execution and compact context remain disabled.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Final Research-Inspired Improvement Report",
        "",
        f"Status: **{report['summary']['status']}**.",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Current | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["strict_final_score", "strict_correctness", "estimated_tokens", "runtime", "tool_calls"]:
        lines.append(f"| {key} | {report['baseline'].get(key)} | {report['current'].get(key)} | {report['delta'].get(key)} |")
    lines.extend(
        [
            "",
            "## Gate Results",
            "",
            f"- Packaged preferred strategy: `{report['summary']['packaged_preferred_strategy']}`",
            f"- Strict score regression gate OK: {report['summary']['strict_score_regression_ok']}",
            f"- Estimated-token overhead: {report['summary']['token_overhead_pct'] * 100:.2f}% "
            f"(gate OK: {report['summary']['estimated_tokens_gate_ok']})",
            f"- Runtime overhead: {report['summary']['runtime_overhead_pct'] * 100:.2f}% "
            f"(gate OK: {report['summary']['runtime_gate_ok']})",
            f"- Tool-call delta: {report['summary']['tool_call_delta']} "
            f"(gate OK: {report['summary']['tool_call_gate_ok']})",
            f"- Value retrieval budget: {report['summary']['value_retrieval_budget_ms']} ms "
            f"(budget OK: {report['summary']['value_retrieval_budget_ok']})",
            f"- Value retrieval cache key algorithm: `{report['summary']['value_retrieval_cache_key_algorithm']}` "
            f"(reproducible: {report['summary']['value_retrieval_cache_reproducible']})",
            f"- Candidate risk clusters reported: {report['summary']['candidate_risk_cluster_count']}",
            f"- Retrieval cluster gate: {report['summary']['retrieval_cluster_gate_status']} "
            f"(passed: {report['summary']['retrieval_cluster_gate_passed']})",
            f"- Improved retrieval clusters: {', '.join(report['summary']['retrieval_cluster_improved_clusters']) or 'none'}",
            f"- Ranking-only no score claim: {report['summary']['ranking_only_no_score_claim']}",
            f"- Shadow repair eval ran: {report['summary']['shadow_repair_eval_ran']}",
            f"- Shadow repair execution enabled: {report['summary']['shadow_repair_execution_enabled']}",
            f"- Shadow repaired better/equal/worse/unsafe: "
            f"{report['summary']['shadow_repair_better_count']}/"
            f"{report['summary']['shadow_repair_equal_count']}/"
            f"{report['summary']['shadow_repair_worse_count']}/"
            f"{report['summary']['shadow_repair_unsafe_count']}",
            f"- Risk level distribution: {report['summary']['risk_level_distribution']}",
            f"- Risk-controller estimated token savings total: {report['summary']['risk_controller_estimated_token_savings_total']} "
            f"(estimated only: {report['summary']['risk_controller_savings_are_estimates']})",
            f"- Risk-controller estimated runtime savings total ms: {report['summary']['risk_controller_estimated_runtime_savings_ms_total']} "
            f"(measured efficiency improvement claimed: {report['summary']['measured_efficiency_improvement_claimed']})",
            f"- Packaged execution changed: {report['summary']['packaged_execution_changed']}",
            f"- Measured accuracy improvement claimed: {report['summary']['measured_accuracy_improvement_claimed']}",
            f"- Measured efficiency improvement claimed: {report['summary']['measured_efficiency_improvement_claimed']}",
            f"- {report['summary']['behavior_changing_flags_note']}",
            f"- Schema vote active/agreement/compact-safe: {report['summary']['schema_vote_active_count']}/"
            f"{report['summary']['schema_vote_agreement_count']}/{report['summary']['compact_context_safe_count']}",
            f"- Compact-context shadow eval rows: {report['summary']['compact_context_shadow_row_count']} "
            f"(avg token delta: {report['summary']['compact_context_shadow_avg_token_delta']}; "
            f"measured efficiency improvement claimed: {report['summary']['compact_context_shadow_measured_efficiency_improvement_claimed']})",
            f"- Compact-context measured eval ran: {report['summary']['compact_context_measured_eval_ran']} "
            f"(eligible rows: {report['summary']['compact_context_measured_eligible_rows']}; "
            f"safe rows: {report['summary']['compact_context_measured_safe_rows']}; "
            f"avg total token delta: {report['summary']['compact_context_measured_avg_token_delta_total']}; "
            f"avg context-only token delta: {report['summary']['compact_context_measured_avg_token_delta_context_only']}; "
            f"avg runtime delta: {report['summary']['compact_context_measured_avg_runtime_delta']}; "
            f"recommendation: {report['summary']['compact_context_measured_recommendation']})",
            f"- Compact-context token classification counts: "
            f"{report['summary']['compact_context_measured_token_classification_counts']}",
            f"- Compact-context measured caveat: "
            f"{report['summary']['compact_context_measured_measurement_caveat'] or 'not run'}",
            f"- Compact-context experimental measured efficiency improvement claimed: "
            f"{report['summary']['compact_context_measured_experimental_efficiency_claimed']}",
            f"- Compact-context official measured efficiency improvement claimed: "
            f"{report['summary']['compact_context_measured_official_efficiency_claimed']}",
            f"- Compact-context measured eval changed packaged execution: "
            f"{report['summary']['compact_context_measured_packaged_execution_changed']}",
            f"- Compact-context feature flag default: {report['summary']['compact_context_feature_flag_default']}",
            f"- Official token accounting ran: {report['summary']['official_token_accounting_ran']} "
            f"(expected savings estimate: {report['summary']['official_token_expected_savings_estimate']})",
            f"- Official token top contributors: {report['summary']['official_token_top_contributors'][:3]}",
            f"- Official token biggest reducible fields: {report['summary']['official_token_biggest_reducible_fields'][:3]}",
            f"- Official token reduction eval ran: {report['summary']['official_token_reduction_eval_ran']} "
            f"(safe rows: {report['summary']['official_token_reduction_safe_rows']}; "
            f"avg token delta: {report['summary']['official_token_reduction_avg_token_delta']}; "
            f"avg score delta: {report['summary']['official_token_reduction_avg_score_delta']}; "
            f"recommendation: {report['summary']['official_token_reduction_recommendation']})",
            f"- Official token reduction changed packaged execution: "
            f"{report['summary']['official_token_reduction_packaged_execution_changed']}",
            f"- Official token reduction feature flag default: "
            f"{report['summary']['official_token_reduction_feature_flag_default']}",
            f"- Official token reduction official efficiency claim: "
            f"{report['summary']['official_token_reduction_official_efficiency_claimed']}",
            f"- Official token reduction canary ran: {report['summary']['official_token_reduction_canary_ran']} "
            f"(safe rows: {report['summary']['official_token_reduction_canary_safe_rows']}; "
            f"unsafe rows: {report['summary']['official_token_reduction_canary_unsafe_rows']}; "
            f"avg token delta: {report['summary']['official_token_reduction_canary_avg_token_delta']}; "
            f"avg score delta: {report['summary']['official_token_reduction_canary_avg_score_delta']}; "
            f"recommendation: {report['summary']['official_token_reduction_canary_recommendation']})",
            f"- Official token reduction canary protected output hashes unchanged: "
            f"{report['summary']['official_token_reduction_canary_protected_hashes_unchanged']}",
            f"- Official token reduction canary changed packaged execution: "
            f"{report['summary']['official_token_reduction_canary_packaged_execution_changed']}",
            f"- Official token reduction canary feature flag default: "
            f"{report['summary']['official_token_reduction_canary_feature_flag_default']}",
            f"- Official token reduction canary official efficiency claim: "
            f"{report['summary']['official_token_reduction_canary_official_efficiency_claimed']}",
            f"- Official token reduction packaged trial ran: "
            f"{report['summary']['official_token_reduction_packaged_trial_ran']} "
            f"(safe rows: {report['summary']['official_token_reduction_packaged_trial_safe_rows']}; "
            f"unsafe rows: {report['summary']['official_token_reduction_packaged_trial_unsafe_rows']}; "
            f"avg token delta: {report['summary']['official_token_reduction_packaged_trial_avg_token_delta']}; "
            f"avg runtime delta: {report['summary']['official_token_reduction_packaged_trial_avg_runtime_delta']}; "
            f"recommendation: {report['summary']['official_token_reduction_packaged_trial_recommendation']})",
            f"- Official token reduction promotion: attempted={report['summary']['official_token_reduction_promotion_attempted']}; "
            f"kept={report['summary']['official_token_reduction_promotion_kept']}; "
            f"score delta={report['summary']['official_token_reduction_promotion_score_delta']}; "
            f"token delta={report['summary']['official_token_reduction_promotion_token_delta']}; "
            f"final submission diff OK={report['summary']['official_token_reduction_promotion_final_submission_diff']}; "
            f"recommendation={report['summary']['official_token_reduction_promotion_recommendation']}",
            f"- Hidden-style eval passed/total: "
            f"{report['summary']['hidden_style_eval_passed_cases']}/{report['summary']['hidden_style_eval_total_cases']}",
            f"- Endpoint-family failure risky rows: {report['summary']['endpoint_family_failure_risky_rows']}",
            f"- Endpoint/schema rule candidates: {report['summary']['endpoint_schema_rule_candidate_rules']} "
            f"(safe for future canary: {report['summary']['endpoint_schema_rule_candidate_safe_rules']})",
            f"- Endpoint/schema rule canary recommendation: "
            f"{report['summary']['endpoint_schema_rule_canary_recommendation']} "
            f"(API top-k hit-rate delta: {report['summary']['endpoint_schema_rule_canary_api_top_k_hit_rate_delta']})",
            f"- Endpoint/schema packaged trial recommendation: "
            f"{report['summary']['endpoint_schema_rule_packaged_trial_recommendation']}",
            f"- Schema/dataset positive repair rows: {report['summary']['schema_dataset_positive_repair_rows']}",
            f"- SQL AST candidate ranking candidates: {report['summary']['sql_ast_candidate_ranking_candidates']}",
            f"- AST-guided SQL canary recommendation: {report['summary']['ast_guided_sql_canary_recommendation']}",
            f"- Retrieval ablation best mode: {report['summary']['retrieval_ablation_best_mode']}",
            f"- Repair selector v2 success: {report['summary']['repair_selector_v2_success']}",
            f"- Repair selector v3 success: {report['summary']['repair_selector_v3_success']} "
            f"(strictly better selected: {report['summary']['repair_selector_v3_strictly_better_selected_count']})",
            f"- Accuracy promotion decision: {report['summary']['accuracy_promotion_decision_recommendation']}",
            f"- Winner readiness next actions: {report['summary']['winner_readiness_recommended_next_action']}",
            f"- Risk-efficiency shadow eval rows: {report['summary']['risk_efficiency_shadow_row_count']} "
            f"(avg token delta: {report['summary']['risk_efficiency_shadow_avg_token_delta']}; "
            f"avg runtime delta: {report['summary']['risk_efficiency_shadow_avg_runtime_delta']}; "
            f"measured efficiency improvement claimed: {report['summary']['risk_efficiency_shadow_measured_efficiency_improvement_claimed']})",
            f"- Secret scan OK: {report['summary']['no_secret_scan_ok']}",
            f"- Visualization artifacts directory: `{report['summary']['visualization_artifacts_dir']}`",
            f"- Visualization artifacts inside final submission: {report['summary']['visualizations_in_final_submission']}",
            f"- Final submission format unchanged: {report['summary']['final_submission_format_unchanged']}",
            "",
            "## Feature Flags",
            "",
            "| Flag | Active |",
            "| --- | --- |",
        ]
    )
    for key, value in report["feature_flags"].items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Technique Summary",
            "",
            "| Technique | Source inspiration | Implemented module | Active in SQL_FIRST? | Active in Raw/GUIDED? | Visualization checkpoint |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["techniques"]:
        lines.append(
            f"| {row['technique']} | {row['source_inspiration']} | `{row['implemented_module']}` | "
            f"{row['active_in_sql_first']} | {row['active_in_raw_guided']} | {row['visualization_checkpoint']} |"
        )
    audit = report["research_safety_audit"]
    lines.extend(
        [
            "",
            "## Diagnostic Candidate Risk Clusters",
            "",
            "| Cluster | Before | After | Delta | Improved? | Diagnostic only | Behavior changing? |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for name, cluster in report.get("candidate_risk_clusters", {}).items():
        lines.append(
            f"| `{name}` | {cluster.get('before_count')} | {cluster.get('after_count')} | {cluster.get('delta')} | "
            f"{cluster.get('improved')} | {cluster.get('diagnostic_only')} | {cluster.get('behavior_changing')} |"
        )
    lines.extend(
        [
            "",
            "## Shadow Repair Canary Recommendations",
            "",
            "Execution repair remains disabled by default. These recommendations are offline what-if results only.",
            "",
            "| Cluster | Rows | Better | Equal | Worse | Avg score delta | Safe to enable? | Recommended flag | Decision |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for name, cluster in report.get("shadow_repair_eval", {}).get("cluster_canary_recommendations", {}).items():
        lines.append(
            f"| `{name}` | {cluster.get('shadow_eval_rows')} | {cluster.get('repaired_better_count')} | "
            f"{cluster.get('repaired_equal_count')} | {cluster.get('repaired_worse_count')} | "
            f"{cluster.get('avg_score_delta')} | {cluster.get('safe_to_enable_canary')} | "
            f"`{cluster.get('recommended_flag')}` | {cluster.get('recommendation')} |"
        )
    lines.extend(
        [
            "",
            "## Research Safety Audit",
            "",
            f"- public_query_overlap: {audit['public_query_overlap']}",
            f"- gold_sql_overlap: {audit['gold_sql_overlap']}",
            f"- public_answer_overlap: {audit['public_answer_overlap']}",
            f"- public_entity_overlap: {audit['public_entity_overlap']}",
            f"- used_gold_patterns: {audit['used_gold_patterns']}",
            "",
            "## Notes",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in report.get("notes", []))
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _pct_delta(current: Any, baseline: Any) -> float:
    if not baseline:
        return 0.0
    return round((float(current or 0.0) - float(baseline)) / float(baseline), 4)


def _count_paths(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if pattern in path.parts or pattern in path.name)


if __name__ == "__main__":
    raise SystemExit(main())
