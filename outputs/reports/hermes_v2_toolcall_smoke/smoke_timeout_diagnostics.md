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
| pure_concept_schema | True | False | None | 21.2 | 20.719 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 15.85 | 15.345 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 37.056 | 18.959 | 0.0 | 0.0 | 0.004 | 0.0 | 17.488 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 37.652 | 32.118 | 0.0 | 0.0 | 0.001 | 0.0 | 4.949 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 34.833 | 26.343 | 0.0 | 0.0 | 0.002 | 0.0 | 7.749 | 0.0 | 0.0 | 2 | 0 | 2 |
| mixed_inactive_journeys | True | False | None | 49.511 | 28.941 | 0.0 | 0.0 | 0.002 | 0.0 | 15.923 | 0.0 | 0.0 | 1 | 1 | 2 |
| compare_local_live_birthday_status | True | False | None | 39.23 | 30.136 | 0.0 | 0.0 | 0.001 | 0.0 | 8.353 | 0.0 | 0.0 | 1 | 1 | 1 |
