# DeepSeek V2 Planner Profile Sweep

- Scope: planner-only, no SQL/API execution.
- row_count: `35`
- selected_profile: `deepseek_micro_tools`
- selection_reason: `selected by max validation_ok_count, max semantic_ir_present_count, valid contracts, min timeout_count, no text fallback, lower latency, and smaller schema.`

## Profile Summary

| Profile | Rows | Semantic IR | Timeouts | Validation OK | Answer Contract | Raw Text | Avg Sec | Tool Schema Chars | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| current | 7 | 2 | 5 | 2 | 0 | 0 | 15.136 | 2217 | {'none': 2, 'planner_timeout': 5} |
| deepseek_auto_tool | 7 | 5 | 2 | 2 | 0 | 0 | 54.87 | 2217 | {'none': 2, 'parse_error': 3, 'planner_timeout': 2} |
| deepseek_required_tool | 7 | 5 | 2 | 4 | 2 | 0 | 46.999 | 2215 | {'none': 3, 'planner_timeout': 2, 'parse_error': 2} |
| deepseek_micro_tools | 7 | 7 | 0 | 5 | 3 | 0 | 37.687 | 2215 | {'none': 5, 'unknown_field': 1, 'planner_error': 1} |
| deepseek_json_tool | 7 | 6 | 1 | 0 | 0 | 0 | 64.907 | 425 | {'planner_timeout': 1, 'parse_error': 6} |

## Rows

| Profile | Prompt | Timeout | Sec | Tool Calls | Tool | Finish | Semantic IR | Tasks | Contract | Valid | Error |
|---|---|---|---:|---:|---|---|---|---:|---|---|---|
| current | pure_concept_schema | False | 13.919 | 1 | submit_semantic_ir_plan | stop | True | 1 | False | True | None |
| current | pure_meta_list_schemas | False | 16.354 | 1 | submit_semantic_ir_plan | stop | True | 1 | False | True | None |
| current | ambiguous_user_schemas | True | 100.003 | 0 | None | None | False | 0 | False | False | planner_timeout |
| current | local_schema_count | True | 100.004 | 0 | None | None | False | 0 | False | False | planner_timeout |
| current | birthday_message_published | True | 100.003 | 0 | None | None | False | 0 | False | False | planner_timeout |
| current | mixed_inactive_journeys | True | 100.004 | 0 | None | None | False | 0 | False | False | planner_timeout |
| current | compare_local_live_birthday_status | True | 100.004 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_auto_tool | pure_concept_schema | False | 23.529 | 1 | submit_semantic_ir_plan | tool_calls | True | 1 | False | True | None |
| deepseek_auto_tool | pure_meta_list_schemas | False | 23.607 | 1 | submit_semantic_ir_plan | tool_calls | True | 1 | False | True | None |
| deepseek_auto_tool | ambiguous_user_schemas | False | 74.244 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | False | False | parse_error |
| deepseek_auto_tool | local_schema_count | False | 73.921 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | False | False | parse_error |
| deepseek_auto_tool | birthday_message_published | False | 79.049 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | False | False | parse_error |
| deepseek_auto_tool | mixed_inactive_journeys | True | 100.004 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_auto_tool | compare_local_live_birthday_status | True | 100.006 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_required_tool | pure_concept_schema | False | 18.134 | 1 | submit_semantic_ir_plan | tool_calls | True | 1 | False | True | None |
| deepseek_required_tool | pure_meta_list_schemas | False | 16.594 | 1 | submit_semantic_ir_plan | tool_calls | True | 1 | False | True | None |
| deepseek_required_tool | ambiguous_user_schemas | True | 100.003 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_required_tool | local_schema_count | False | 94.0 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | False | False | parse_error |
| deepseek_required_tool | birthday_message_published | False | 59.069 | 1 | submit_semantic_ir_plan | tool_calls | True | 1 | True | True | parse_error |
| deepseek_required_tool | mixed_inactive_journeys | False | 47.198 | 1 | submit_semantic_ir_plan | tool_calls | True | 2 | True | True | None |
| deepseek_required_tool | compare_local_live_birthday_status | True | 100.003 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_micro_tools | pure_concept_schema | False | 20.399 | 1 | submit_direct_task | tool_calls | True | 1 | False | True | None |
| deepseek_micro_tools | pure_meta_list_schemas | False | 11.852 | 1 | submit_direct_task | tool_calls | True | 1 | False | True | None |
| deepseek_micro_tools | ambiguous_user_schemas | False | 19.11 | 1 | submit_local_query_task | tool_calls | True | 1 | True | True | None |
| deepseek_micro_tools | local_schema_count | False | 16.364 | 1 | submit_local_count_task | tool_calls | True | 1 | True | True | None |
| deepseek_micro_tools | birthday_message_published | False | 53.793 | 1 | submit_local_lookup_task | tool_calls | True | 1 | False | False | unknown_field |
| deepseek_micro_tools | mixed_inactive_journeys | False | 50.738 | 1 | submit_mixed_evidence_plan | tool_calls | True | 2 | True | True | None |
| deepseek_micro_tools | compare_local_live_birthday_status | False | 91.552 | 0 | None | None | True | 0 | False | False | planner_error |
| deepseek_json_tool | pure_concept_schema | True | 100.004 | 0 | None | None | False | 0 | False | False | planner_timeout |
| deepseek_json_tool | pure_meta_list_schemas | False | 46.954 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
| deepseek_json_tool | ambiguous_user_schemas | False | 58.071 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
| deepseek_json_tool | local_schema_count | False | 66.519 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
| deepseek_json_tool | birthday_message_published | False | 56.056 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
| deepseek_json_tool | mixed_inactive_journeys | False | 82.752 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
| deepseek_json_tool | compare_local_live_birthday_status | False | 79.087 | 1 | submit_semantic_ir_json | stop | True | 0 | False | False | parse_error |
