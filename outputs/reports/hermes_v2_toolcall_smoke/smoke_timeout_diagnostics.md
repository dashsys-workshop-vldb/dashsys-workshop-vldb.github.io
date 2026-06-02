# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_failures: `0`
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
| pure_concept_schema | True | False | None | 11.575 | 7.619 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 5.99 | 5.436 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | False | False | None | 12.349 | 9.522 | 0.0 | 0.0 | 0.001 | 0.0 | 2.194 | 0.0 | 0.0 | 1 | 0 | 0 |
| local_schema_count | False | False | None | 13.848 | 10.881 | 0.0 | 0.0 | 0.001 | 0.0 | 2.329 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | False | False | None | 37.454 | 33.103 | 0.0 | 0.0 | 0.001 | 0.0 | 3.355 | 0.0 | 0.0 | 1 | 0 | 0 |
| mixed_inactive_journeys | True | False | None | 40.046 | 33.578 | 0.0 | 0.0 | 0.002 | 0.0 | 3.717 | 0.0 | 0.0 | 1 | 0 | 3 |
| compare_local_live_birthday_status | False | False | None | 82.986 | 36.52 | 0.0 | 0.0 | 0.001 | 0.0 | 3.407 | 0.0 | 0.0 | 1 | 1 | 0 |
