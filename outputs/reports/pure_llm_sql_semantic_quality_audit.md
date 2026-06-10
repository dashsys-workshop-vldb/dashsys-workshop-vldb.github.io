# Pure LLM SQL Semantic Quality Audit

Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

- Rows audited: `5`
- Answer used SQL result rows: `1`
- SQL evidence object available rows: `1`
- SQL evidence used in answer rows: `1`

## Failure Categories
- `no_executable_sql`: `4`
- `wrong_table`: `1`

## Row Root Causes
### example_000
- Prompt: When was the journey 'Birthday Message' published?
- Previous failure category: `wrong_columns`
- Failure category: `no_executable_sql`
- Selected candidate: `None` / count `3`
- SQL evidence object available / used: `False` / `False`
- SQL score / answer score: `0.0` / `0.2176`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

### example_001
- Prompt: Give me inactive journeys
- Previous failure category: `no_executable_sql`
- Failure category: `no_executable_sql`
- Selected candidate: `None` / count `3`
- SQL evidence object available / used: `False` / `False`
- SQL score / answer score: `0.0` / `0.1739`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

### example_002
- Prompt: List all journeys
- Previous failure category: `wrong_table`
- Failure category: `wrong_table`
- Selected candidate: `1` / count `3`
- SQL evidence object available / used: `True` / `True`
- SQL score / answer score: `0.0` / `0.3278`
- Root cause: The SQL plan passed validation but selected a table or SQL shape that did not match the requested local entity.

### example_003
- Prompt: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- Previous failure category: `sql_result_not_used`
- Failure category: `no_executable_sql`
- Selected candidate: `None` / count `3`
- SQL evidence object available / used: `False` / `False`
- SQL score / answer score: `0.0` / `0.2553`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

### example_004
- Prompt: Show me the IDs of failed dataflow runs
- Previous failure category: `no_executable_sql`
- Failure category: `no_executable_sql`
- Selected candidate: `None` / count `3`
- SQL evidence object available / used: `False` / `False`
- SQL score / answer score: `0.0` / `0.2131`
- Root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
