# System Summary

- Preferred strategy: `SQL_FIRST_API_VERIFY`
- Packaged strict score: `0.6553`
- Best isolated score: `0.6558`
- Hidden-style: `48/48`
- Final submission ready: `True`
- Official-token reduction enabled: `True`
- Repair execution enabled: `False`
- Compact context enabled: `False`
- Final recommendation: `ready_to_submit_with_official_token_reduction`
- Live Adobe API readiness: `warning` (smoke `skipped_live_credentials_missing`, pipeline `skipped_live_credentials_missing`)
- Post-permission live verification: `complete`; waiting-status report: `complete`
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`; packaged runtime affected: `False`
- Decision-stage feedback loops: stages mapped `20`, semantic-router recommendation `candidate_not_viable_after_feedback_loops`
- Evidence-aware answer synthesis: `keep_trial_only` (trial `complete`)
- Score-focused core path trials: `keep_trial_only`; best delta `0.0`; runtime change applied: `False`
- Context7 docs audit: `complete`; runtime change applied: `False`

## Workflow

- Prompt normalization and query analysis
- Metadata/context selection
- SQL_FIRST_API_VERIFY planning
- Validated SQL/API execution
- Evidence extraction, answer synthesis, verification, and packaging

## Source Reports

- `outputs/eval_results_strict.json`
- `outputs/winner_readiness_report.json`
- `outputs/hidden_style_eval.json`
- `outputs/official_token_reduction_promotion_report.json`
- `outputs/reports/post_permission_live_api_verification.md`
- `outputs/reports/adobe_access_waiting_status.md`
- `outputs/reports/context7_code_alignment_audit.md`
- `outputs/reports/context7_fix_decision.md`
- `outputs/reports/score_path_contribution_audit.md`
- `outputs/reports/score_focused_core_improvement_trials.md`
- `outputs/reports/score_focused_core_fix_decision.md`
