# Pure LLM Bounded SQL Score Audit

Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Summary
- Rows audited: `5`
- Average SQL score: `0.18`
- Root cause: `bounded_sql_score_requires_row_level_review`
- Explanation: SQL score is not uniformly zero in the audited rows.

## Failure Categories
- `api_used_when_sql_needed`: `1`
- `sql_result_not_used_in_answer`: `1`
- `sql_valid_but_wrong_columns`: `1`
- `sql_valid_but_wrong_table`: `1`
- `tool_trace_format_mismatch`: `1`

## Rows
### example_000
- Prompt: When was the journey 'Birthday Message' published?
- Failure category: `sql_valid_but_wrong_columns`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `None` / `0.0052`
- SQL reason: Strict SQL mismatch.
- Compiled SQL: `SELECT "UPDATEDTIME" FROM "dim_campaign" WHERE "dim_campaign"."NAME" = 'Birthday Message' LIMIT 50`
- Deterministic comparison: `same_table_different_filter`

### example_001
- Prompt: Give me inactive journeys
- Failure category: `tool_trace_format_mismatch`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `0.0` / `0.1739`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

### example_002
- Prompt: List all journeys
- Failure category: `sql_valid_but_wrong_table`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `0.0` / `0.1009`
- SQL reason: Strict SQL mismatch.
- Compiled SQL: `SELECT "CAMPAIGNID", "UPDATEDTIME", "STARTDATE", "IMSORGID" FROM "dim_campaign" WHERE "dim_campaign"."CAMPAIGNID" = NULL LIMIT 50`
- Deterministic comparison: `same_table_different_filter`

### example_003
- Prompt: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- Failure category: `sql_result_not_used_in_answer`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.9` / `0.0` / `0.2553`
- SQL reason: Strict semantic result match.
- Compiled SQL: `SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT" FROM "dim_segment" WHERE "dim_segment"."ISACCOUNTSEGMENT" = 'Y' AND "dim_segment"."UPDATEDTIME" = NULL LIMIT 50`
- Deterministic comparison: `wrong_table`

### example_004
- Prompt: Show me the IDs of failed dataflow runs
- Failure category: `api_used_when_sql_needed`
- SQL called: `False`; API called: `True`
- Strict SQL/API/answer: `0.0` / `None` / `0.2029`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`
