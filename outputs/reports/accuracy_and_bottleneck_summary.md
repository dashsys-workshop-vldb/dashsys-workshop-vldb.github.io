# Accuracy And Bottleneck Summary

- Starting score: `0.6491`
- Best isolated score: `0.6558`
- 0.70 target reached: `False`
- 0.75 target reached: `False`
- Answer-quality bottleneck: `True`
- Dry-run API limitation: `True`
- Live Adobe API readiness: `pass`; infrastructure validation only: `True`
- Supportable rewrite status: `safe_for_autonomous_packaged_trial`
- Endpoint tie-break status: `keep_shadow_only`
- AST canary status: `keep_shadow_only`
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`
- Decision-stage feedback-loop status: `candidate_not_viable_after_feedback_loops`
- Evidence-aware answer synthesis: `keep_trial_only`; answer-only invariant enforced: `True`
- Score-focused core path trials: `keep_trial_only`; best strict delta `0.0`; runtime change applied `False`
- Comprehensive failure analysis: `wait_for_adobe_access`; rule candidates `5`; runtime change applied `False`
- Type-specific deterministic rules: `speed_only_candidate`; candidate families `8`; runtime change applied `False`
- SDK tool-calling optimization: `speed_only_shadow_candidates_no_promotion`; best projected strict delta `0.0`; runtime change applied `False`
- Correctness + efficiency evaluation: `speed_only_patch_needs_validation`; best candidate `compact_tool_schema`; runtime change applied `False`
- SDK tool-calling efficiency promotion: `promoted_speed_only_patch`; promotion accepted `True`; runtime change applied `True`
- Core tool policy optimizer: `promoted_core_tool_efficiency_policy`; strict after projected `0.6553`; runtime change expected `True`

## Why Changes Remain Shadow-Only

- The 0.70 and 0.75 targets were not reached safely.
- Live Adobe API readiness is now the primary API-path infrastructure target; dry-run wording remains fallback polish.
- Endpoint/schema and AST changes are report-only or shadow-only unless strict gates improve.
- The LLM semantic routing helper is default-off and remains shadow-only unless a later strict/safety gate promotes it.
