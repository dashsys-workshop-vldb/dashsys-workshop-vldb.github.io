# Consolidated Report Index

Start here. Most older generated reports were consolidated or removed.

## Canonical Reports

- [system_summary.md](system_summary.md)
- [llm_baseline_summary.md](llm_baseline_summary.md)
- [accuracy_and_bottleneck_summary.md](accuracy_and_bottleneck_summary.md)
- [visualization_summary.md](visualization_summary.md)
- [overnight_autonomous_improvement_report.md](overnight_autonomous_improvement_report.md)
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
- [outputs/visualizations/sql_prompt_storyboard_primary.md](../visualizations/sql_prompt_storyboard_primary.md)
- [outputs/visualizations/system_status_dashboard.md](../visualizations/system_status_dashboard.md)
- [outputs/visualizations/technique_visual_cards.md](../visualizations/technique_visual_cards.md)
- [outputs/visualizations/end_to_end_system_dataflow.md](../visualizations/end_to_end_system_dataflow.md)
- [outputs/visualizations/score_bottleneck_dashboard.md](../visualizations/score_bottleneck_dashboard.md)

## Diagnostic Prompt Coverage

- `outputs/reports/generated_prompt_suite_summary.md` - Diagnostic prompt coverage only; not official strict score.
- `outputs/reports/diagnostic_prompt_suite_run.md` - Diagnostic prompt runtime coverage only; not official strict score.

## System-Wide SDK LLM Audit

- `outputs/reports/sdk_usage_audit.md`
- Runtime LLM direct HTTP hits: `0`

## Live Adobe API Readiness

- Readiness audit: `outputs/reports/live_adobe_api_readiness_audit.md`
- API_REQUIRED readiness matrix: `outputs/reports/api_required_readiness_matrix.md`
- Smoke report: `outputs/reports/live_api_readiness_smoke.md`
- Evidence pipeline trial: `outputs/reports/live_api_evidence_pipeline_trial.md`
- Mock live evidence pipeline trial: `outputs/reports/mock_live_api_evidence_pipeline_trial.md`
- Overall status: `warning`
- Credentials present in latest smoke: `False`
- Live mode attempted: `False`
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

## Post-Change Validation Contract

Skipped commands must record command, reason, substitute validation, and residual risk.

Required commands:
- `python3 -m pytest -q`
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
- `outputs/reports/live_api_evidence_pipeline_trial.md/json`
- `outputs/reports/mock_live_api_evidence_pipeline_trial.md/json`
- `outputs/reports/evidence_usage_audit.md/json`
- `outputs/reports/evidence_aware_answer_rewrite_trial.md/json`
- `outputs/reports/feedback_loop_answer_synthesis_final.md/json`
- `outputs/reports/sql_evidence_usage_audit.md/json`
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
- `outputs/visualizations/index.md/json`
- `outputs/visualizations/system_status_dashboard.md/json`
- `outputs/visualizations/technique_visual_cards.md/json`

## Current Status

- preferred_strategy: `SQL_FIRST_API_VERIFY`
- packaged_strict_score: `0.6553`
- best_isolated_score: `0.6558`
- hidden_style: `48/48`
- final_submission_ready: `True`
- live_adobe_api_readiness: `warning`
- evidence_aware_answer_synthesis: `keep_trial_only`
- llm_recommendation: `keep_shadow_only`
- target_0_75_reached: `False`
