# Pure LLM SQL Zero Root Cause Analysis

Diagnostic-only analysis. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

- Rows considered: `259`
- SQL failure rows: `79`
- Dominant category: `no_sql_called_when_needed`
- Cause: SQL score is primarily zero because the agent did not call execute_sql when SQL evidence was needed.

## Failure Categories

- `hallucinated_column`: `15`
- `hallucinated_table`: `9`
- `no_clear_sql_failure`: `1`
- `no_sql_called_when_needed`: `27`
- `sql_called_but_invalid`: `3`
- `wrong_sql_shape`: `24`

## Promising Fixes

- retrieval-ranked structured SQL candidates with semantic verification
- SQL reviewer/repair loop using compiler, validator, and execution-probe feedback
- evidence-source planner and tool-choice validation
