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
| pure_concept_schema | True | False | None | 6.987 | 6.498 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 5.739 | 5.374 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 29.886 | 10.101 | 0.0 | 0.0 | 0.003 | 0.0 | 8.079 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 13.056 | 10.088 | 0.0 | 0.0 | 0.001 | 0.0 | 2.417 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 19.503 | 12.58 | 0.0 | 0.0 | 0.002 | 0.0 | 2.876 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | True | False | None | 21.437 | 12.499 | 0.0 | 0.0 | 0.001 | 0.0 | 5.842 | 0.0 | 0.0 | 1 | 0 | 2 |
| compare_local_live_birthday_status | True | False | None | 36.677 | 28.84 | 0.0 | 0.0 | 0.002 | 0.0 | 6.974 | 0.0 | 0.0 | 2 | 2 | 1 |
