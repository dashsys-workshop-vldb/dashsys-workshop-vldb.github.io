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
| pure_concept_schema | True | False | None | 18.81 | 18.578 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 10.07 | 9.865 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 30.724 | 12.68 | 0.0 | 0.0 | 0.001 | 0.0 | 8.769 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 26.308 | 23.737 | 0.0 | 0.0 | 0.001 | 0.0 | 2.301 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 20.772 | 16.298 | 0.0 | 0.0 | 0.001 | 0.0 | 3.889 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | True | False | None | 41.966 | 20.455 | 0.0 | 0.0 | 0.001 | 0.0 | 8.907 | 0.0 | 0.0 | 1 | 0 | 2 |
| compare_local_live_birthday_status | True | False | None | 27.715 | 22.478 | 0.0 | 0.0 | 0.001 | 0.0 | 4.663 | 0.0 | 0.0 | 1 | 1 | 1 |
