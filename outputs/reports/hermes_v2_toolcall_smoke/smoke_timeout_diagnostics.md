# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `2`
- unsupported_claims: `0`
- no_tool_fp: `3`
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
| pure_concept_schema | True | False | None | 9.253 | 8.047 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 6.738 | 5.688 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | False | False | None | 49.192 | 48.09 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| local_schema_count | False | False | None | 28.975 | 23.309 | 0.0 | 0.0 | 0.001 | 0.0 | 4.205 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | False | True | checkpoint_llm_owned_pass_graph_gate | 180.005 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| mixed_inactive_journeys | False | True | checkpoint_llm_unified_planner_start | 180.015 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| compare_local_live_birthday_status | False | False | None | 139.171 | 62.888 | 0.0 | 0.0 | 0.001 | 0.0 | 5.595 | 0.0 | 0.0 | 1 | 1 | 0 |
