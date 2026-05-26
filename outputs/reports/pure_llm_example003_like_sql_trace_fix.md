# Pure LLM Example003-Like SQL Trace Fix Audit

Diagnostic-only audit for bounded rows where SQL was expected but no executable SQL reached strict scoring.

- Example003-like row count: `2`
- Rows with compiled SQL missing from trace: `0`

## Likely Issues
- `compiler_rejected_plan`: `1`
- `repair_loop_failed`: `1`

## Rows
### example_001 / `conservative_sql_first_semantic_v1`
- Executable SQL reached evaluator: `False`
- Likely issue: `repair_loop_failed`
- Fix status: `no_executable_sql_due_to_plan_or_repair_failure`
- Compiled SQL: ``

### example_004 / `conservative_sql_first_semantic_v1`
- Executable SQL reached evaluator: `False`
- Likely issue: `compiler_rejected_plan`
- Fix status: `no_executable_sql_due_to_plan_or_repair_failure`
- Compiled SQL: ``
