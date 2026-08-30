# Live Efficiency Recovery Trials

Diagnostic-only projected variants. No SQL/API evidence or final answers are changed by this report.

- Baseline strict score: `0.6567`
- Non-regression reference: `0.6553`
- Best variant: `compact_repeated_checkpoint_metadata`
- Best projected strict score: `0.6575`
- Recommendation: `promote_efficiency_recovery_fix`

## Variants

- `compact_api_preview_strict`: projected `0.6572`, token delta `-59.5143`, recommendation `candidate_for_runtime_validation`
- `evidencebus_projection_for_answer_context`: projected `0.6567`, token delta `0.0`, recommendation `candidate_for_runtime_validation`
- `compact_repeated_checkpoint_metadata`: projected `0.6575`, token delta `-98.3429`, recommendation `candidate_for_runtime_validation`
- `api_response_summary_only_for_live_success`: projected `0.6569`, token delta `-22.3714`, recommendation `candidate_for_runtime_validation`
- `live_get_session_reuse`: projected `0.6569`, token delta `0.0`, recommendation `candidate_for_runtime_validation`
- `identical_get_memoization_trial`: projected `0.6567`, token delta `0.0`, recommendation `do_not_promote_without_stronger_evidence`
- `optional_api_suppression_when_sql_complete_trial`: projected `0.6567`, token delta `0.0`, recommendation `do_not_promote_without_stronger_evidence`
