# Pure LLM Bounded SQL Score Audit

Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Summary
- Rows audited: `5`
- Average SQL score: `0.0`
- Root cause: `bounded_sql_score_zero_due_to_missing_or_invalid_sql_calls`
- Explanation: at least one SQL trace was not visible to the evaluator; 1 row(s) emitted SQL that did not match gold SQL semantics.

## Failure Categories
- `sql_valid_but_wrong_table`: `1`
- `tool_trace_format_mismatch`: `4`

## Rows
### example_000
- Prompt: When was the journey 'Birthday Message' published?
- Failure category: `tool_trace_format_mismatch`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `None` / `0.2176`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

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
- Strict SQL/API/answer: `0.0` / `0.0` / `0.3278`
- SQL reason: Strict SQL mismatch.
- Compiled SQL: `SELECT "CAMPAIGNID", "UPDATEDTIME", "STARTDATE", "IMSORGID" FROM "dim_campaign" LIMIT 50`
- Deterministic comparison: `same_table_different_filter`

### example_003
- Prompt: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- Failure category: `tool_trace_format_mismatch`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `0.0` / `0.2553`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

### example_004
- Prompt: Show me the IDs of failed dataflow runs
- Failure category: `tool_trace_format_mismatch`
- SQL called: `True`; API called: `False`
- Strict SQL/API/answer: `0.0` / `None` / `0.2131`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`
