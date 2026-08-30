# Final Gate Safe Fixes To Keep

- `APIValidator unresolved query-parameter placeholder blocking`: keep=`true`. Prevents invalid API calls with placeholder params from reaching Adobe; current strict correctness/API/answer scores did not regress under normal token-reduction runs. Score tradeoff: No behavior-score drop observed; may still be logged as failed API evidence for audit rather than sent over network.
- `Token reduction preserves unresolved-parameter warnings`: keep=`true`. Required by readiness audit to distinguish blocked unresolved params from silent omission. Score tradeoff: No isolated warning-preservation score drop observed; disabling the full token-reduction feature is a broader behavior change and lowers score.
- `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE trial wiring`: keep=`true`. Useful isolated trial strategy, but not packaged default after final-gate baseline drift. Score tradeoff: Keep trial-only until baseline stability is re-established.

Packaged default remains `SQL_FIRST_API_VERIFY`; combined_safe remains trial-only.
