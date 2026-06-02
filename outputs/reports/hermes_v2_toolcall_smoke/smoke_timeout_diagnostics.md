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
| pure_concept_schema | True | False | None | 18.752 | 18.498 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 9.957 | 9.725 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 31.587 | 12.621 | 0.0 | 0.0 | 0.002 | 0.0 | 9.298 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 28.788 | 26.02 | 0.0 | 0.0 | 0.001 | 0.0 | 2.429 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 21.815 | 17.486 | 0.0 | 0.0 | 0.001 | 0.0 | 3.69 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | True | False | None | 43.162 | 21.981 | 0.0 | 0.0 | 0.001 | 0.0 | 8.62 | 0.0 | 0.0 | 1 | 0 | 2 |
| compare_local_live_birthday_status | True | False | None | 27.059 | 21.944 | 0.0 | 0.0 | 0.001 | 0.0 | 4.521 | 0.0 | 0.0 | 1 | 1 | 1 |
