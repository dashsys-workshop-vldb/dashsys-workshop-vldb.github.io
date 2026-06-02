# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `False`
- fresh_smoke_passed: `False`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `2`
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
| pure_concept_schema | True | False | None | 12.728 | 9.377 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 9.119 | 8.558 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | False | False | None | 54.767 | 23.006 | 0.0 | 0.0 | 0.0 | 0.0 | 2.685 | 0.0 | 0.0 | 0 | 0 | 0 |
| local_schema_count | False | False | None | 70.711 | 26.102 | 0.0 | 0.0 | 0.0 | 0.0 | 17.361 | 0.0 | 0.0 | 0 | 0 | 0 |
