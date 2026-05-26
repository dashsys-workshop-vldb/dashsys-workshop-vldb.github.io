# Pure LLM Example003-Like SQL Trace Fix Audit

Diagnostic-only audit for bounded rows where SQL was expected but no executable SQL reached strict scoring.

- Example003-like row count: `1`
- Rows with compiled SQL missing from trace: `0`

## Likely Issues
- `repair_loop_failed`: `1`

## Rows
### example_001 / `api_only_only_when_sql_unavailable_v1`
- Executable SQL reached evaluator: `False`
- Likely issue: `repair_loop_failed`
- Fix status: `no_executable_sql_due_to_plan_or_repair_failure`
- Compiled SQL: ``
