# Pure LLM Bounded SQL Score Audit

Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Summary
- Rows audited: `5`
- Average SQL score: `0.0`
- Root cause: `bounded_sql_score_zero_due_to_missing_or_invalid_sql_calls`
- Explanation: 4 row(s) used API while gold SQL existed; at least one SQL trace was not visible to the evaluator.

## Failure Categories
- `api_used_when_sql_needed`: `4`
- `tool_trace_format_mismatch`: `1`

## Rows
### example_000
- Prompt: When was the journey 'Birthday Message' published?
- Failure category: `api_used_when_sql_needed`
- SQL called: `False`; API called: `True`
- Strict SQL/API/answer: `0.0` / `None` / `0.2388`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

### example_001
- Prompt: Give me inactive journeys
- Failure category: `api_used_when_sql_needed`
- SQL called: `False`; API called: `True`
- Strict SQL/API/answer: `0.0` / `0.83` / `0.1795`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

### example_002
- Prompt: List all journeys
- Failure category: `api_used_when_sql_needed`
- SQL called: `False`; API called: `True`
- Strict SQL/API/answer: `0.0` / `0.83` / `0.0261`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`

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
- Failure category: `api_used_when_sql_needed`
- SQL called: `False`; API called: `True`
- Strict SQL/API/answer: `0.0` / `None` / `0.2029`
- SQL reason: No generated SQL while gold SQL exists.
- Compiled SQL: ``
- Deterministic comparison: `answer_did_not_use_sql`
