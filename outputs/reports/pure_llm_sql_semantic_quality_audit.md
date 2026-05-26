# Pure LLM SQL Semantic Quality Audit

Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

- Rows audited: `5`
- Answer used SQL result rows: `0`

## Failure Categories
- `no_executable_sql`: `2`
- `sql_result_not_used`: `1`
- `wrong_columns`: `1`
- `wrong_table`: `1`

## Row Root Causes
### example_000
- Prompt: When was the journey 'Birthday Message' published?
- Failure category: `wrong_columns`
- SQL score / answer score: `0.0` / `0.2176`
- Root cause: The SQL plan selected an updated timestamp instead of a published timestamp such as LASTDEPLOYEDTIME.

### example_001
- Prompt: Give me inactive journeys
- Failure category: `no_executable_sql`
- SQL score / answer score: `0.0` / `0.1739`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

### example_002
- Prompt: List all journeys
- Failure category: `wrong_table`
- SQL score / answer score: `0.0` / `0.3392`
- Root cause: The SQL plan passed validation but selected a table or SQL shape that did not match the requested local entity.

### example_003
- Prompt: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- Failure category: `sql_result_not_used`
- SQL score / answer score: `0.9` / `0.2553`
- Root cause: The SQL query produced useful rows, but final answer synthesis ignored or underused those rows.

### example_004
- Prompt: Show me the IDs of failed dataflow runs
- Failure category: `no_executable_sql`
- SQL score / answer score: `0.0` / `0.2131`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
