# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `True`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_failures: `0`
- raw_sql_fallback_used_count: `0`
- dev_eval_ran: `False`
- dev_eval_blocked_reason: ``
- safe_to_keep: `True`
- safe_to_commit: `True`
- safe_to_benchmark: `True`
- safe_to_promote: `False`

## Per-Prompt Latency

| Prompt | Pass | Timeout | Timed Out Stage | Total Sec | Planner Sec | SQL Gate Sec | API Gate Sec | SQL Exec Sec | API Exec Sec | Final Composer Sec | Repair Sec | Final Gate Sec | SQL | API | Facts |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_concept_schema | True | False | None | 16.801 | 16.454 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 9.643 | 9.41 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 32.336 | 12.38 | 0.0 | 0.0 | 0.004 | 0.0 | 9.867 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 29.456 | 26.291 | 0.0 | 0.0 | 0.001 | 0.0 | 2.82 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 22.967 | 18.644 | 0.0 | 0.0 | 0.002 | 0.0 | 3.603 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | True | False | None | 46.676 | 21.808 | 0.0 | 0.0 | 0.003 | 0.0 | 10.093 | 0.0 | 0.0 | 1 | 0 | 2 |
| compare_local_live_birthday_status | True | False | None | 38.636 | 29.816 | 0.0 | 0.0 | 0.001 | 0.0 | 8.003 | 0.0 | 0.0 | 1 | 1 | 1 |
