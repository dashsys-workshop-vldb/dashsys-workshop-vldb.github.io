# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `1`
- unsupported_claims: `0`
- no_tool_fp: `1`
- final_semantic_gate_failures: `0`
- raw_sql_fallback_used_count: `0`
- dev_eval_ran: `False`
- dev_eval_blocked_reason: `fresh smoke did not meet pass criteria`
- safe_to_keep: `True`
- safe_to_commit: `False`
- safe_to_benchmark: `False`
- safe_to_promote: `False`

## Per-Prompt Latency

| Prompt | Pass | Timeout | Timed Out Stage | Total Sec | Planner Sec | SQL Gate Sec | API Gate Sec | SQL Exec Sec | API Exec Sec | Final Composer Sec | Repair Sec | Final Gate Sec | SQL | API | Facts |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_concept_schema | True | False | None | 63.897 | 63.382 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 27.056 | 26.722 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 53.694 | 28.369 | 0.0 | 0.0 | 0.002 | 0.0 | 24.785 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 33.867 | 27.356 | 0.0 | 0.0 | 0.001 | 0.0 | 6.099 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | True | False | None | 43.134 | 34.703 | 0.0 | 0.0 | 0.001 | 0.0 | 7.602 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | True | False | None | 91.506 | 70.643 | 0.0 | 0.0 | 0.001 | 0.0 | 8.694 | 0.0 | 0.0 | 1 | 0 | 2 |
| compare_local_live_birthday_status | False | True | checkpoint_llm_unified_planner_start | 120.002 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
