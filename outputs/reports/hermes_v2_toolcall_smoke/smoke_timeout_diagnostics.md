# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `4`
- unsupported_claims: `0`
- no_tool_fp: `5`
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
| pure_concept_schema | True | False | None | 30.668 | 28.589 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | False | False | None | 67.429 | 37.169 | 0.0 | 0.0 | 0.0 | 0.0 | 3.815 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | False | False | None | 90.413 | 39.543 | 0.0 | 0.0 | 0.0 | 0.0 | 3.211 | 0.0 | 0.0 | 0 | 0 | 0 |
| local_schema_count | False | True | checkpoint_llm_final_answer_composer_start | 120.004 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| birthday_message_published | False | True | checkpoint_llm_unified_planner_start | 120.006 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| mixed_inactive_journeys | False | True | checkpoint_llm_owned_pass_graph_repair_start | 120.003 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| compare_local_live_birthday_status | False | True | checkpoint_llm_owned_pass_graph_repair_start | 120.004 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
