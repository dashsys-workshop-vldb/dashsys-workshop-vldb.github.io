# Consolidated Report Index

Start here. Most older generated reports were consolidated or removed.

## Canonical Reports

- [system_summary.md](system_summary.md)
- [llm_baseline_summary.md](llm_baseline_summary.md)
- [accuracy_and_bottleneck_summary.md](accuracy_and_bottleneck_summary.md)
- [visualization_summary.md](visualization_summary.md)
- [core_tool_optimization_audit.md](core_tool_optimization_audit.md)
- [core_tool_policy_optimizer.md](core_tool_policy_optimizer.md)
- [core_tool_compiled_policy_candidate.md](core_tool_compiled_policy_candidate.md)
- [core_tool_correctness_audit.md](core_tool_correctness_audit.md)
- [core_tool_correctness_trials.md](core_tool_correctness_trials.md)
- [core_tool_correctness_fix_decision.md](core_tool_correctness_fix_decision.md)
- [overnight_autonomous_improvement_report.md](overnight_autonomous_improvement_report.md)
- [repo_cleanup_result.md](repo_cleanup_result.md)
- [report_index.md](report_index.md)

## Key Source-Of-Truth Reports

- `outputs/eval_results_strict.json`
- `outputs/winner_readiness_report.md`
- `outputs/final_research_inspired_improvement_report.md`
- `outputs/hidden_style_eval.md`
- `outputs/llm_strict_baseline_eval.md`

## Key Visualizations

- [outputs/visualizations/executive_dashboard.md](../visualizations/executive_dashboard.md)
- [outputs/visualizations/end_to_end_system_dataflow.html](../visualizations/end_to_end_system_dataflow.html)
- [outputs/visualizations/full_project_dataflow.svg](../visualizations/full_project_dataflow.svg)
- [outputs/visualizations/full_project_dataflow.md](../visualizations/full_project_dataflow.md)
- [outputs/visualizations/project_architecture_c4.md](../visualizations/project_architecture_c4.md)
- [outputs/visualizations/end_to_end_pipeline_mermaid.md](../visualizations/end_to_end_pipeline_mermaid.md)
- [outputs/visualizations/live_adobe_api_status_mermaid.md](../visualizations/live_adobe_api_status_mermaid.md)
- [outputs/visualizations/report_generation_map.md](../visualizations/report_generation_map.md)
- [outputs/visualizations/sql_prompt_storyboard_primary.md](../visualizations/sql_prompt_storyboard_primary.md)
- [outputs/visualizations/system_status_dashboard.md](../visualizations/system_status_dashboard.md)
- [outputs/visualizations/technique_visual_cards.md](../visualizations/technique_visual_cards.md)
- [outputs/visualizations/end_to_end_system_dataflow.md](../visualizations/end_to_end_system_dataflow.md)
- [outputs/visualizations/score_bottleneck_dashboard.md](../visualizations/score_bottleneck_dashboard.md)

## Diagnostic Prompt Coverage

- `outputs/reports/generated_prompt_suite_summary.md` - Diagnostic prompt coverage only; not official strict score.
- `outputs/reports/diagnostic_prompt_suite_run.md` - Diagnostic prompt runtime coverage only; not official strict score.
- `outputs/reports/generated_prompt_suite_local_diagnostic.md` - Local dry-run 250-prompt diagnostic only; no live API calls or official score claim.
- `outputs/reports/generated_prompt_local_gap_samples.md` - Representative local diagnostic gap samples; advisory-only and not promotion evidence.
- `outputs/reports/local_deterministic_improvement_candidates.md` - Evidence-gated deterministic improvement candidates; no automatic runtime change.
- `outputs/reports/superpowers_next_steps_preflight.md` - Superpowers-style protected-artifact preflight before any local deterministic improvement.
- `outputs/reports/local_gap_manual_review.md` - Manual review of high-value local diagnostic gaps; generated labels are advisory only.
- `outputs/reports/superpowers_fix_decision.md` - Evidence-gated fix decision; no runtime change unless exactly one safe candidate passes.
- `outputs/reports/full_generated_prompt_suite_diagnostic.md` - Full 250-prompt generated suite diagnostic only; no official strict score claim.
- `outputs/reports/generated_prompt_coverage_gap_analysis.md` - Generated prompt coverage gaps; diagnostic-only and not promotion evidence.

## Live Adobe Organizer Smoke

- `outputs/reports/organizer_adobe_ups_audiences_smoke.md` - Safe implementation of the organizer client-credentials plus UPS audiences smoke snippet; credentials and headers are redacted.

## Schema-Aware SQL Diagnostics

- `outputs/reports/sql_template_coverage_audit.md` - Template hit/miss audit across public/dev and generated diagnostic prompts.
- `outputs/reports/nl_sql_robustness_audit.md` - Robustness-first NL-to-SQL audit across deterministic paraphrase/synonym/order variants.
- `outputs/reports/nl_sql_paraphrase_consistency.md` - Per-semantic-group route/table/join/count/intent/SQL-shape consistency report.
- `outputs/reports/multi_llm_backend_robustness.md` - Backend-sensitivity status report; records no-hosted-call deterministic baseline and unavailable backends.
- `outputs/reports/schema_aware_sql_feedback_loop.md` - Robustness-gated promotion decision for schema-aware SQL fallback.
- `outputs/reports/robustness_first_system_summary.md` - System summary stating score is not meaningful unless robustness gates pass.
- `outputs/reports/schema_aware_sql_trial.md` - Isolated schema-aware SQL fallback trial; decision `keep_trial_only`, no packaged runtime promotion.

## LLM Controller Diagnostics

- Failure decomposition: `outputs/reports/llm_controller_failure_decomposition.md`
- Rewrite ablation: `outputs/reports/controller_rewrite_ablation.md`
- Controller status: `shadow_only`
- Automatic promotion: `False`
- Recommendation: `controller_no_rewrite_better`

## System-Wide SDK LLM Audit

- `outputs/reports/sdk_usage_audit.md`
- Runtime LLM direct HTTP hits: `0`

## SDK Tool Calling Optimization

- Preflight: `outputs/reports/sdk_tool_calling_optimization_preflight.md`
- Tool-call surface audit: `outputs/reports/sdk_tool_call_surface_audit.md`
- Decision analysis: `outputs/reports/sdk_tool_call_decision_analysis.md`
- Variants: `outputs/reports/sdk_tool_call_optimization_variants.md`
- Isolated trials: `outputs/reports/sdk_tool_calling_optimization_trials.md`
- Fix decision: `outputs/reports/sdk_tool_calling_fix_decision.md`
- Decision: `speed_only_shadow_candidates_no_promotion`
- Runtime change applied: `False`
- Direct HTTP hits: `0`
- These reports are shadow-only SDK/tool-call policy analysis; SQL_FIRST_API_VERIFY remains packaged default.

## Correctness + Efficiency Evaluation

- Scorecard: `outputs/reports/correctness_efficiency_scorecard.md`
- Fix decision: `outputs/reports/correctness_efficiency_fix_decision.md`
- Decision: `speed_only_patch_needs_validation`
- Best candidate: `compact_tool_schema`
- Official overall score claim: `False`
- Organizer weights known: `False`
- Runtime change applied: `False`
- Correctness-only strict score is not treated as the full organizer evaluation picture.

## SDK Tool Calling Efficiency Promotion

- Preflight: `outputs/reports/sdk_tool_calling_promotion_preflight.md`
- Plan: `outputs/reports/sdk_tool_calling_promotion_plan.md`
- Decision: `outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md`
- Decision status: `promoted_speed_only_patch`
- Runtime change applied: `True`
- Promotion accepted: `True`
- Direct HTTP hits: `0`
- This is a speed-only SDK/tool-call patch; SQL_FIRST_API_VERIFY remains the packaged default.

## Core Tool Policy Optimizer

- Tool audit: `outputs/reports/core_tool_optimization_audit.md`
- Search space: `outputs/reports/core_tool_optimization_search_space.md`
- Optimizer: `outputs/reports/core_tool_policy_optimizer.md`
- Search results: `outputs/reports/core_tool_policy_search_results.md`
- execute_sql candidates: `outputs/reports/execute_sql_optimization_candidates.md`
- call_api candidates: `outputs/reports/call_api_optimization_candidates.md`
- Compiled candidate: `outputs/reports/core_tool_compiled_policy_candidate.md`
- Promotion decision: `outputs/reports/core_tool_policy_promotion_decision.md`
- Decision: `promoted_core_tool_efficiency_policy`
- Runtime change expected in repo: `True`
- This optimizer is restricted to execute_sql/call_api internals; SQL_FIRST_API_VERIFY remains packaged default.

## DASHSys Project Skill

- Skill: `skills/dashsys_project_skill/SKILL.md`
- Audit: `outputs/reports/dashsys_project_skill_audit.md`
- Overall status: `pass`
- Runtime behavior changed: `False`
- Env local accessed: `False`
- Use this repo-local Skill before serious Codex changes; it separates correctness, efficiency, live API, reporting, packaging, and security work.

## Context7 Documentation-Grounded Audit

- Preflight: `outputs/reports/context7_docs_audit_preflight.md`
- Dependency docs summary: `outputs/reports/context7_dependency_docs_summary.md`
- Code alignment audit: `outputs/reports/context7_code_alignment_audit.md`
- Fix decision: `outputs/reports/context7_fix_decision.md`
- Status: `complete`
- Dependencies reviewed: `8`
- Code changes applied: `False`
- External SDK/API changes require Context7 documentation lookup first; Context7 secrets must never be printed.

## Score-Focused Direct Path Trials

- Contribution audit: `outputs/reports/score_path_contribution_audit.md`
- Isolated trials: `outputs/reports/score_focused_core_improvement_trials.md`
- Fix decision: `outputs/reports/score_focused_core_fix_decision.md`
- Recommendation: `keep_trial_only`
- Best strict delta: `0.0`
- Runtime change applied: `False`
- These reports use the SVG only as a score-path map; visualization changes are not score improvements.

## Comprehensive Failure Analysis

- Preflight: `outputs/reports/comprehensive_failure_analysis_preflight.md`
- Official row table: `outputs/reports/official_row_failure_table.md`
- Generated prompt table: `outputs/reports/generated_prompt_failure_table.md`
- Cross-dataset clusters: `outputs/reports/cross_dataset_failure_clusters.md`
- Rule candidates: `outputs/reports/general_deterministic_rule_candidates.md`
- Hardcoding risk audit: `outputs/reports/general_rule_hardcoding_risk_audit.md`
- Fix decision: `outputs/reports/comprehensive_failure_fix_decision.md`
- Decision: `wait_for_adobe_access`
- Runtime change applied: `False`
- Generated prompts used for: `generality_and_coverage_only`
- Official strict rows diagnose real score loss; generated prompts provide coverage/generalization evidence only.

## Type-Specific Deterministic Rules

- Prompt-type audit: `outputs/reports/deterministic_prompt_type_audit.md`
- Rule candidates: `outputs/reports/type_specific_deterministic_rule_candidates.md`
- Isolated trials: `outputs/reports/type_specific_deterministic_rule_trials.md`
- Fix decision: `outputs/reports/type_specific_rule_fix_decision.md`
- Decision: `speed_only_candidate`
- Candidate count: `8`
- Trial count: `8`
- Runtime change applied: `False`
- Rules are grouped by prompt type, domain, answer intent, execution need, and evidence shape.

## Live Adobe API Readiness

- Readiness audit: `outputs/reports/live_adobe_api_readiness_audit.md`
- API_REQUIRED readiness matrix: `outputs/reports/api_required_readiness_matrix.md`
- Smoke report: `outputs/reports/live_api_readiness_smoke.md`
- Endpoint path diagnosis: `outputs/reports/live_api_endpoint_path_diagnosis.md`
- External blockers: `outputs/reports/live_api_external_blockers.md`
- Follow-up commands: `outputs/reports/live_api_endpoint_followup_commands.md`
- Full-run blocker: `outputs/reports/live_api_full_run_blocker.md`
- Post-permission verification: `outputs/reports/post_permission_live_api_verification.md`
- Adobe access waiting status: `outputs/reports/adobe_access_waiting_status.md`
- Evidence pipeline trial: `outputs/reports/live_api_evidence_pipeline_trial.md`
- Mock live evidence pipeline trial: `outputs/reports/mock_live_api_evidence_pipeline_trial.md`
- Overall status: `pass`
- Credentials present in latest smoke: `True`
- Live mode attempted: `True`
- Full live strict eval blocked: `False`
- Full generated prompt suite blocked: `False`
- Mock parser success count: `126`
- Mock discovery chains simulated: `5`
- Live API readiness is infrastructure validation only; it is not official strict-score evidence.
- `API_REQUIRED` remains required in live mode; dry-run remains an honest fallback when credentials are missing.

## LLM Semantic Routing Helper

- `outputs/reports/llm_semantic_router_shadow_eval.md`
- Feature flag default: `off`
- Shadow-only by default: `true`
- Uses SDK-based `LLMClient`; no direct HTTP; routing hints only; no final answers.
- Status: `complete`
- Isolated trial: `complete`
- Isolated trial report: `outputs/reports/llm_semantic_router_isolated_trial.md`
- Promotion decision report: `outputs/reports/llm_semantic_router_promotion_decision.md`
- Packaged runtime affected: `False`
- Recommendation: `do_not_promote`

## Decision-Stage Audit And Feedback Loops

- Workflow decision map: `outputs/reports/workflow_decision_map.md`
- Workflow decision audit: `outputs/reports/workflow_decision_audit.md`
- Feedback-loop index: `outputs/reports/improvement_feedback_loop_index.md`
- Semantic-router loop final: `outputs/reports/feedback_loop_semantic_router_final.md`
- Decision-stage improvement summary: `outputs/reports/decision_stage_improvement_summary.md`
- Stages mapped: `20`
- Audited rows: `35`
- Semantic-router feedback recommendation: `candidate_not_viable_after_feedback_loops`
- Generated diagnostic prompts remain coverage-only and are not promotion evidence.

## Evidence-Aware Answer Synthesis

- Evidence usage audit: `outputs/reports/evidence_usage_audit.md`
- Answer rewrite trial: `outputs/reports/evidence_aware_answer_rewrite_trial.md`
- Feedback-loop final: `outputs/reports/feedback_loop_answer_synthesis_final.md`
- SQL evidence usage audit: `outputs/reports/sql_evidence_usage_audit.md`
- Confidence calibration audit: `outputs/reports/confidence_calibration_audit.md`
- Token efficiency audit: `outputs/reports/token_efficiency_audit.md`
- Trial status: `complete`
- Recommendation: `keep_trial_only`
- Answer-only invariant enforced: `True`
- Answer-only promotion requires invariant SQL/API/tool/evidence hashes, hidden-style 48/48, readiness pass, and no unsupported-claim increase.

## Workshop Requirement Alignment

- [workshop_requirement_audit.md](workshop_requirement_audit.md)
- Overall status: `pass`
- Critical failures: `0`

## Cleanup Reports

- `outputs/reports/cleanup_audit.md`
- `outputs/reports/cleanup_final_report.md`
- `outputs/reports/repo_cleanup_preflight.md`
- `outputs/reports/repo_cleanup_candidate_inventory.md`
- `outputs/reports/repo_cleanup_deletion_plan.md`
- `outputs/reports/repo_cleanup_result.md`

## Post-Change Validation Contract

Skipped commands must record command, reason, substitute validation, and residual risk.

Required commands:
- `python3 -m pytest -q`
- `python3 scripts/audit_dashsys_project_skill.py`
- `python3 scripts/generate_end_to_end_system_dataflow.py`
- `python3 scripts/audit_workshop_requirements.py`
- `python3 scripts/run_dev_eval.py --strict`
- `python3 scripts/run_hidden_style_eval.py`
- `python3 scripts/audit_live_adobe_api_readiness.py`
- `python3 scripts/generate_api_required_readiness_matrix.py`
- `python3 scripts/run_live_api_readiness_smoke.py`
- `python3 scripts/run_live_api_evidence_pipeline_trial.py`
- `python3 scripts/run_mock_live_api_evidence_pipeline_trial.py`
- `python3 scripts/run_evidence_usage_audit.py`
- `python3 scripts/run_evidence_aware_answer_rewrite_trial.py`
- `python3 scripts/run_sql_evidence_usage_audit.py`
- `python3 scripts/run_score_path_contribution_audit.py`
- `python3 scripts/run_score_focused_core_improvement_trials.py`
- `python3 scripts/run_comprehensive_failure_analysis.py`
- `python3 scripts/run_deterministic_prompt_type_audit.py`
- `python3 scripts/run_type_specific_deterministic_rule_trials.py`
- `python3 scripts/run_sdk_tool_calling_optimization_audit.py`
- `python3 scripts/run_sdk_tool_calling_optimization_trials.py`
- `python3 scripts/run_correctness_efficiency_scorecard.py`
- `python3 scripts/run_sdk_tool_calling_efficiency_promotion.py --validation-complete`
- `python3 scripts/run_tool_calling_policy_optimizer.py`
- `python3 scripts/run_core_tool_optimization_audit.py`
- `python3 scripts/run_core_tool_policy_optimizer.py`
- `python3 scripts/audit_repo_cleanup_candidates.py`
- `python3 scripts/run_confidence_calibration_audit.py`
- `python3 scripts/run_token_efficiency_audit.py`
- `python3 scripts/check_llm_sdk_backend.py`
- `python3 scripts/run_workflow_decision_audit.py`
- `python3 scripts/run_decision_feedback_loop.py`
- `python3 scripts/run_llm_baseline_eval.py`
- `python3 scripts/run_llm_strict_baseline_eval.py`
- `python3 scripts/run_llm_hidden_style_diagnostic.py`
- `python3 scripts/generate_winner_readiness_report.py`
- `python3 scripts/generate_research_inspired_report.py`
- `python3 scripts/generate_system_status_dashboard.py`
- `python3 scripts/generate_technique_visual_cards.py`
- `python3 scripts/generate_project_mermaid_visualizations.py`
- `python3 scripts/generate_full_project_dataflow_svg.py`
- `python3 scripts/generate_visualization_index.py`
- `python3 scripts/package_submission.py`
- `python3 scripts/package_query_outputs.py`
- `python3 scripts/check_submission_ready.py`

Regenerated report surfaces:
- `outputs/reports/report_index.md/json`
- `outputs/reports/system_summary.md/json`
- `outputs/reports/llm_baseline_summary.md/json`
- `outputs/reports/accuracy_and_bottleneck_summary.md/json`
- `outputs/reports/visualization_summary.md/json`
- `outputs/reports/workshop_requirement_audit.md/json`
- `outputs/reports/live_adobe_api_readiness_audit.md/json`
- `outputs/reports/api_required_readiness_matrix.md/json`
- `outputs/reports/live_api_readiness_smoke.md/json`
- `outputs/reports/context7_docs_audit_preflight.md/json`
- `outputs/reports/context7_dependency_docs_summary.md/json`
- `outputs/reports/context7_code_alignment_audit.md/json`
- `outputs/reports/context7_fix_decision.md/json`
- `outputs/reports/live_api_evidence_pipeline_trial.md/json`
- `outputs/reports/mock_live_api_evidence_pipeline_trial.md/json`
- `outputs/reports/evidence_usage_audit.md/json`
- `outputs/reports/evidence_aware_answer_rewrite_trial.md/json`
- `outputs/reports/feedback_loop_answer_synthesis_final.md/json`
- `outputs/reports/sql_evidence_usage_audit.md/json`
- `outputs/reports/score_path_contribution_audit.md/json`
- `outputs/reports/score_focused_core_improvement_trials.md/json`
- `outputs/reports/score_focused_core_fix_decision.md/json`
- `outputs/reports/comprehensive_failure_analysis_preflight.md/json`
- `outputs/reports/official_row_failure_table.md/json`
- `outputs/reports/generated_prompt_failure_table.md/json`
- `outputs/reports/cross_dataset_failure_clusters.md/json`
- `outputs/reports/general_deterministic_rule_candidates.md/json`
- `outputs/reports/cross_dataset_counterfactual_answer_sketches.md/json`
- `outputs/reports/general_rule_hardcoding_risk_audit.md/json`
- `outputs/reports/comprehensive_failure_fix_decision.md/json`
- `outputs/reports/deterministic_prompt_type_audit.md/json`
- `outputs/reports/type_specific_deterministic_rule_candidates.md/json`
- `outputs/reports/type_specific_deterministic_rule_trials.md/json`
- `outputs/reports/type_specific_rule_fix_decision.md/json`
- `outputs/reports/sdk_tool_calling_optimization_preflight.md/json`
- `outputs/reports/sdk_tool_call_surface_audit.md/json`
- `outputs/reports/sdk_tool_call_decision_analysis.md/json`
- `outputs/reports/sdk_tool_call_optimization_variants.md/json`
- `outputs/reports/sdk_tool_calling_optimization_trials.md/json`
- `outputs/reports/sdk_tool_calling_fix_decision.md/json`
- `outputs/reports/correctness_efficiency_scorecard.md/json`
- `outputs/reports/correctness_efficiency_fix_decision.md/json`
- `outputs/reports/sdk_tool_calling_promotion_preflight.md/json`
- `outputs/reports/sdk_tool_calling_promotion_plan.md/json`
- `outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md/json`
- `outputs/reports/tool_calling_policy_optimizer.md/json`
- `outputs/reports/tool_calling_objective_functions.md/json`
- `outputs/reports/tool_calling_policy_search_results.md/json`
- `outputs/reports/tool_calling_compiled_policy_candidate.md/json`
- `outputs/reports/tool_calling_policy_promotion_decision.md/json`
- `outputs/reports/core_tool_optimization_audit.md/json`
- `outputs/reports/core_tool_optimization_search_space.md/json`
- `outputs/reports/core_tool_policy_optimizer.md/json`
- `outputs/reports/core_tool_policy_search_results.md/json`
- `outputs/reports/execute_sql_optimization_candidates.md/json`
- `outputs/reports/call_api_optimization_candidates.md/json`
- `outputs/reports/core_tool_compiled_policy_candidate.md/json`
- `outputs/reports/core_tool_policy_promotion_decision.md/json`
- `outputs/reports/repo_cleanup_preflight.md/json`
- `outputs/reports/repo_cleanup_candidate_inventory.md/json`
- `outputs/reports/repo_cleanup_deletion_plan.md/json`
- `outputs/reports/repo_cleanup_result.md/json`
- `outputs/reports/dashsys_project_skill_audit.md/json`
- `outputs/reports/confidence_calibration_audit.md/json`
- `outputs/reports/token_efficiency_audit.md/json`
- `outputs/reports/workflow_decision_map.md/json`
- `outputs/reports/workflow_decision_audit.md/json`
- `outputs/reports/improvement_feedback_loop_index.md/json`
- `outputs/reports/feedback_loop_semantic_router_final.md/json`
- `outputs/reports/decision_stage_improvement_summary.md/json`
- `outputs/reports/cleanup_audit.md/json`
- `outputs/reports/cleanup_final_report.md/json`
- `outputs/winner_readiness_report.md/json`
- `outputs/final_research_inspired_improvement_report.md/json`
- `outputs/visualizations/end_to_end_system_dataflow.html`
- `outputs/visualizations/end_to_end_system_dataflow.md/json`
- `outputs/visualizations/project_architecture_c4.md/mmd`
- `outputs/visualizations/end_to_end_pipeline_mermaid.md/mmd`
- `outputs/visualizations/live_adobe_api_status_mermaid.md/mmd`
- `outputs/visualizations/report_generation_map.md/mmd`
- `outputs/visualizations/full_project_dataflow.svg`
- `outputs/visualizations/full_project_dataflow.md/json`
- `outputs/reports/full_project_dataflow_svg_audit.md/json`
- `outputs/visualizations/index.md/json`
- `outputs/visualizations/system_status_dashboard.md/json`
- `outputs/visualizations/technique_visual_cards.md/json`
- `outputs/reports/visualization_sync_audit.md/json`

## Current Status

- preferred_strategy: `SQL_FIRST_API_VERIFY`
- packaged_strict_score: `0.6553`
- best_isolated_score: `0.6558`
- hidden_style: `48/48`
- final_submission_ready: `True`
- live_adobe_api_readiness: `pass`
- evidence_aware_answer_synthesis: `keep_trial_only`
- llm_recommendation: `keep_shadow_only`
- sdk_tool_calling_optimization: `speed_only_shadow_candidates_no_promotion`
- correctness_efficiency_evaluation: `speed_only_patch_needs_validation`
- sdk_tool_calling_efficiency_promotion: `promoted_speed_only_patch`
- core_tool_policy_optimizer: `promoted_core_tool_efficiency_policy`
- repo_cleanup: `validated`
- dashsys_project_skill: `pass`
- context7_docs_audit: `complete`
- target_0_75_reached: `False`
