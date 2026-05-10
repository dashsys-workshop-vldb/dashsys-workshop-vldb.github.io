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

- `outputs/visualizations/executive_dashboard.md`
- `outputs/visualizations/sql_prompt_storyboard_primary.md`
- `outputs/visualizations/system_status_dashboard.md`
- `outputs/visualizations/score_bottleneck_dashboard.md`

## Diagnostic Prompt Coverage

- `outputs/reports/generated_prompt_suite_summary.md` - Diagnostic prompt coverage only; not official strict score.
- `outputs/reports/diagnostic_prompt_suite_run.md` - Diagnostic prompt runtime coverage only; not official strict score.

## System-Wide SDK LLM Audit

- `outputs/reports/sdk_usage_audit.md`
- Runtime LLM direct HTTP hits: `0`

## LLM Semantic Routing Helper

- `outputs/reports/llm_semantic_router_shadow_eval.md`
- Feature flag default: `off`
- Shadow-only by default: `true`
- Uses SDK-based `LLMClient`; no direct HTTP; routing hints only; no final answers.
- Status: `complete`
- Recommendation: `keep_shadow_only`

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
- `python3 scripts/audit_workshop_requirements.py`
- `python3 scripts/run_dev_eval.py --strict`
- `python3 scripts/run_hidden_style_eval.py`
- `python3 scripts/check_llm_sdk_backend.py`
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
- `outputs/reports/cleanup_audit.md/json`
- `outputs/reports/cleanup_final_report.md/json`
- `outputs/winner_readiness_report.md/json`
- `outputs/final_research_inspired_improvement_report.md/json`
- `outputs/visualizations/index.md/json`
- `outputs/visualizations/system_status_dashboard.md/json`
- `outputs/visualizations/technique_visual_cards.md/json`

## Current Status

- preferred_strategy: `SQL_FIRST_API_VERIFY`
- packaged_strict_score: `0.6553`
- best_isolated_score: `0.6558`
- hidden_style: `48/48`
- final_submission_ready: `True`
- llm_recommendation: `keep_shadow_only`
- target_0_75_reached: `False`
