# Post-SQL API Decision Trial

Classification: `diagnostic_only`. The trial is shadow-only and did not change API execution.

## Summary

- total_rows: `35`
- post_sql_deterministic_policy_distribution: `{'AMBIGUOUS': 2, 'CALL_API': 19, 'CAVEAT_ONLY': 7, 'SKIP_API': 7}`
- post_sql_policy_confidence_distribution: `{'HIGH': 26, 'LOW': 7, 'MEDIUM': 2}`
- llm_post_sql_advisor_invocation_count: `9`
- llm_advice_verified_count: `0`
- llm_advice_blocked_count: `0`
- api_calls_saved: `15`
- api_calls_added: `0`
- rows_helped_estimate: `15`
- rows_hurt_estimate: `0`
- recommendation: `keep_shadow_only`
