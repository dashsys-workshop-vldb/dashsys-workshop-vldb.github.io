# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `2`
- final_semantic_gate_failures: `2`
- raw_sql_fallback_used_count: `0`
- dev_eval_ran: `False`
- dev_eval_blocked_reason: `fresh smoke did not meet pass criteria`
- safe_to_keep: `True`
- safe_to_commit: `True`
- safe_to_benchmark: `False`
- safe_to_promote: `False`

## Per-Prompt Latency

| Prompt | Pass | Timeout | Timed Out Stage | Total Sec | Planner Sec | SQL Gate Sec | API Gate Sec | SQL Exec Sec | API Exec Sec | Final Composer Sec | Repair Sec | Final Gate Sec | SQL | API | Facts |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_concept_schema | True | False | None | 8.825 | 8.272 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 6.125 | 5.579 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | False | False | None | 15.21 | 9.514 | 0.0 | 0.0 | 0.0 | 0.0 | 2.468 | 0.0 | 0.0 | 0 | 1 | 0 |
| local_schema_count | False | False | None | 14.465 | 11.413 | 0.0 | 0.0 | 0.001 | 0.0 | 2.411 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | False | False | None | 72.433 | 34.947 | 0.0 | 0.0 | 0.0 | 0.0 | 2.007 | 0.0 | 0.0 | 0 | 0 | 0 |
| mixed_inactive_journeys | False | False | None | 72.086 | 34.831 | 0.0 | 0.0 | 0.0 | 0.0 | 2.136 | 0.0 | 0.0 | 0 | 0 | 0 |
| compare_local_live_birthday_status | False | False | None | 50.593 | 39.988 | 0.0 | 0.0 | 0.002 | 0.0 | 4.461 | 0.0 | 0.0 | 1 | 1 | 0 |
