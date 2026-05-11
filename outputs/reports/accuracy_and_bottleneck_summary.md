# Accuracy And Bottleneck Summary

- Starting score: `0.6491`
- Best isolated score: `0.6558`
- 0.70 target reached: `False`
- 0.75 target reached: `False`
- Answer-quality bottleneck: `True`
- Dry-run API limitation: `True`
- Live Adobe API readiness: `warning`; infrastructure validation only: `True`
- Supportable rewrite status: `safe_for_autonomous_packaged_trial`
- Endpoint tie-break status: `keep_shadow_only`
- AST canary status: `keep_shadow_only`
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`
- Decision-stage feedback-loop status: `candidate_not_viable_after_feedback_loops`

## Why Changes Remain Shadow-Only

- The 0.70 and 0.75 targets were not reached safely.
- Live Adobe API readiness is now the primary API-path infrastructure target; dry-run wording remains fallback polish.
- Endpoint/schema and AST changes are report-only or shadow-only unless strict gates improve.
- The LLM semantic routing helper is default-off and remains shadow-only unless a later strict/safety gate promotes it.
