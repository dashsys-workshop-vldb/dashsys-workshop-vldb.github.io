# DeepSeek V2 Planner-Only Diagnostics

- row_count: `7`
- timeout_count: `2`
- semantic_ir_present_count: `5`
- answer_contract_present_count: `0`
- raw_text_content_present_count: `1`

| Prompt | Expected | Timeout | Sec | Tool Calls | Tool | Finish | Semantic IR | Tasks | Profile | Retry | Error |
|---|---|---|---:|---:|---|---|---|---:|---|---|---|
| pure_concept_schema | DIRECT | False | 25.398 | 0 | None | stop | True | 0 | default | False | None |
| pure_meta_list_schemas | DIRECT | False | 33.498 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | default | False | parse_error |
| ambiguous_user_schemas | EVIDENCE_LOCAL | False | 36.864 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | default | False | parse_error |
| local_schema_count | EVIDENCE_SQL | False | 46.982 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | default | False | parse_error |
| birthday_message_published | EVIDENCE_LOCAL | True | 120.004 | 0 | None | None | False | 0 | None | None | planner_timeout |
| mixed_inactive_journeys | EVIDENCE_LOCAL | True | 120.011 | 0 | None | None | False | 0 | None | None | planner_timeout |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | False | 104.745 | 1 | submit_semantic_ir_plan | tool_calls | True | 0 | default | False | parse_error |
