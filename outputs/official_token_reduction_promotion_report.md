# Official Token Reduction Promotion Report

- Promotion attempted: True
- Promotion kept: True
- Recommendation: `promoted_keep_enabled`
- Feature flag default: True
- Explicit disable: `ENABLE_OFFICIAL_TOKEN_REDUCTION=0`

## Metrics

- Strict score: 0.6486 -> 0.6491 (0.0005)
- Correctness: 0.6743 -> 0.6743
- Estimated tokens: 899.2286 -> 831.4571 (-67.7715)
- Runtime: 0.0112 -> 0.0115 (0.0003)
- Tool calls: 1.4571 -> 1.4571 (0.0)

## Gates

- preferred_strategy_sql_first: True
- strict_final_score_gate: True
- strict_correctness_gate: True
- estimated_tokens_gate: True
- tool_calls_gate: True
- final_submission_diff_gate: True
- readiness_gate: True
- no_secret_scan_gate: True
- repair_execution_disabled_gate: True
- compact_context_disabled_gate: True
- official_token_reduction_default_on_gate: True

## Final Submission Diff

- Format unchanged: True
- Preferred strategy: `SQL_FIRST_API_VERIFY`
- Experimental roots included: []

This is now an official packaged improvement only when `recommendation=promoted_keep_enabled`.
