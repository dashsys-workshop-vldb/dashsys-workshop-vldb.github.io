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
| pure_concept_schema | True | False | None | 13.196 | 12.912 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 10.828 | 10.507 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 32.513 | 15.174 | 0.0 | 0.0 | 0.002 | 0.0 | 16.937 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 34.102 | 29.213 | 0.0 | 0.0 | 0.002 | 0.0 | 4.481 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 33.263 | 24.513 | 0.0 | 0.0 | 0.002 | 0.0 | 8.067 | 0.0 | 0.0 | 2 | 0 | 2 |
| mixed_inactive_journeys | True | False | None | 41.886 | 25.598 | 0.0 | 0.0 | 0.001 | 0.0 | 12.361 | 0.0 | 0.0 | 1 | 1 | 2 |
| compare_local_live_birthday_status | True | False | None | 35.476 | 25.242 | 0.0 | 0.0 | 0.001 | 0.0 | 9.555 | 0.0 | 0.0 | 1 | 1 | 1 |
