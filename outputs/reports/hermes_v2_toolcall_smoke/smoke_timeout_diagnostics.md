# Hermes V2 Toolcall Smoke Timeout Diagnostics

- fresh_smoke_completed: `True`
- fresh_smoke_passed: `False`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
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
| pure_concept_schema | True | False | None | 11.71 | 11.42 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| pure_meta_list_schemas | True | False | None | 7.957 | 7.728 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| ambiguous_user_schemas | True | False | None | 45.152 | 12.12 | 0.0 | 0.0 | 0.002 | 0.0 | 32.673 | 0.0 | 0.0 | 1 | 0 | 3 |
| local_schema_count | True | False | None | 27.209 | 20.715 | 0.0 | 0.0 | 0.001 | 0.0 | 6.202 | 0.0 | 0.0 | 1 | 0 | 1 |
| birthday_message_published | False | False | None | 61.127 | 18.965 | 0.0 | 0.0 | 0.001 | 0.0 | 10.129 | 0.0 | 0.0 | 1 | 0 | 1 |
| mixed_inactive_journeys | False | False | None | 90.915 | 20.92 | 0.0 | 0.0 | 0.001 | 0.0 | 27.179 | 0.0 | 0.0 | 1 | 1 | 2 |
| compare_local_live_birthday_status | True | False | None | 46.361 | 24.829 | 0.0 | 0.0 | 0.001 | 0.0 | 20.822 | 0.0 | 0.0 | 1 | 1 | 1 |

## Validation Results

| Check | Result |
|---|---|
| `python3 -m pytest -q` | 1133 passed, 1 skipped |
| `python3 scripts/check_submission_ready.py` | ok=true; default SQL_FIRST_API_VERIFY; query_output_count=73; secret_scan ok |
| `python3 scripts/generate_sdk_usage_audit.py` | runtime_llm_direct_http_hits=0 |
| `git diff --check` | passed |
