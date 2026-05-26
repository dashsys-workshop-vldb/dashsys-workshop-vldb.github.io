# Staged Evidence Policy Trial

Classification: `diagnostic_only`. The trial is shadow-only and did not change packaged `SQL_FIRST_API_VERIFY` execution.

## Summary

- total_prompts: `85`
- branch_distribution: `{'API': 11, 'SQL': 74}`
- second_branch_distribution: `{'API_AFTER_SQL_IF_NEEDED': 11, 'NONE': 74}`
- sql_and_api_both_high_count: `5`
- api_first_count: `11`
- no_tool_branch_count: `0`
- strict_delta: `0.0`
- api_score_delta: `0.0`
- answer_score_delta: `0.0`
- tool_call_delta: `0`
- recommendation: `keep_shadow_only`

## Variants

- `shadow_observe_only`: saved `0`, added `0`, advisor calls `0`
- `deterministic_high_conf_only`: saved `0`, added `0`, advisor calls `0`
- `llm_advisor_medium_low_only`: saved `0`, added `0`, advisor calls `11`
- `combined_verified_policy`: saved `63`, added `0`, advisor calls `11`
- `drop_api_when_sql_direct_answer`: saved `63`, added `0`, advisor calls `0`
- `sql_first_then_api_if_needed`: saved `63`, added `11`, advisor calls `0`
