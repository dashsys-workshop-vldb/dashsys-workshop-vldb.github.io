# DeepSeek V2 Planner Stabilization Report

## Summary

- Selected profile: `deepseek_micro_tools`
- Native SDK toolcall Semantic IR remained primary: `true`
- Atomic/text protocol fallback used: `false`
- Packaged default changed: `false`
- Ready to run dev eval: `false`
- Dev-eval blocker: focused smoke failed: passed_count=5, timeout_count=1, no_tool_fp=1, final_semantic_gate_final_failures=1

## Profile Sweep

| Profile | Rows | Semantic IR | Timeouts | Valid | Answer Contract | Raw Text | Avg Sec | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| current | 7 | 2 | 5 | 2 | 0 | 0 | 15.136 | {'none': 2, 'planner_timeout': 5} |
| deepseek_auto_tool | 7 | 5 | 2 | 2 | 0 | 0 | 54.87 | {'none': 2, 'parse_error': 3, 'planner_timeout': 2} |
| deepseek_required_tool | 7 | 5 | 2 | 4 | 2 | 0 | 46.999 | {'none': 3, 'parse_error': 2, 'planner_timeout': 2} |
| deepseek_micro_tools | 7 | 7 | 0 | 5 | 3 | 0 | 37.687 | {'none': 5, 'planner_error': 1, 'unknown_field': 1} |
| deepseek_json_tool | 7 | 6 | 1 | 0 | 0 | 0 | 64.907 | {'parse_error': 6, 'planner_timeout': 1} |

## Planner-Only Diagnostic

- row_count: `7`
- timeout_count: `0`
- semantic_ir_present_count: `7`
- answer_contract_present_count: `5`
- raw_text_content_present_count: `0`

## Full Smoke

- row_count: `7`
- passed_count: `5`
- failed_count: `2`
- timeout_count: `1`
- unsupported_claims: `0`
- no_tool_fp: `1`
- final_semantic_gate_final_failures: `1`
- sql_calls: `4`
- api_calls: `0`
- raw_sql_fallback_used_count: `0`

| Prompt | Pass | Timeout | SQL | API | Unsupported | no_tool_fp | Final Gate Fail | Error |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pure_concept_schema | True | False | 0 | 0 | 0 | False | 0 | None |
| pure_meta_list_schemas | True | False | 0 | 0 | 0 | False | 0 | None |
| ambiguous_user_schemas | True | False | 1 | 0 | 0 | False | 0 | None |
| local_schema_count | True | False | 1 | 0 | 0 | False | 0 | None |
| birthday_message_published | True | False | 1 | 0 | 0 | False | 0 | None |
| mixed_inactive_journeys | False | False | 1 | 0 | 0 | False | 1 | None |
| compare_local_live_birthday_status | False | True | 0 | 0 | 0 | True | 0 | checkpoint_llm_owned_pass_graph_repair_start |

## Validation

- py_compile: `passed`
- focused_cluster_pytest: `177 passed`
- full_pytest: `1247 passed, 1 skipped`
- check_submission_ready: `ok=true`
- sdk_usage_audit: `runtime_llm_direct_http_hits=0`
- git_diff_check: `passed`
- probe_hermes_sdk_toolcall: `ok=true, toolcall_supported=true, tool_calls_count=1`

## Objective Conclusion

Micro-tools materially improve planner-only behavior for local DeepSeek: planner-only reached 7/7 Semantic IR present with 0 timeouts and no raw text. Full smoke still fails 2/7 rows, so dev eval was not run. V2 remains shadow-only and not promotable.
