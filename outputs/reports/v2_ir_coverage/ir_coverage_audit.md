# Semantic IR Coverage And Raw SQL Fallback

- ok: `True`
- skipped: `False`
- strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- classification: `diagnostic_only`
- smoke_reused: `True`
- primary_path: `SDK toolcall Semantic IR`
- raw_sql_fallback_policy: `Only after valid-but-unsupported local Semantic IR and one Semantic IR repair attempt.`
- backend_semantic_planning_used: `False`
- backend_sql_generation_used: `False`

## Summary

- atomic_protocol_fallback_count: `0`
- backend_generated_sql_count: `0`
- backend_semantic_planning_count: `0`
- final_semantic_gate_final_failures: `0`
- no_tool_fp: `0`
- raw_sql_fallback_considered_count: `0`
- raw_sql_fallback_repair_attempted_count: `0`
- raw_sql_fallback_success_count: `0`
- raw_sql_fallback_used_count: `0`
- raw_sql_safety_gate_failures: `0`
- row_count: `7`
- semantic_ir_support_checked_count: `5`
- semantic_ir_supported_count: `5`
- smoke_ok: `True`
- smoke_skipped: `False`
- support_repair_attempted_count: `0`
- support_repair_success_count: `0`
- unsupported_claims: `0`
- valid_unsupported_ir_count: `0`

## Rows

| Prompt | Support Checked | Supported | Support Repair | Raw Considered | Raw Used | Raw Safe | SQL | API | Facts | Pass |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| pure_concept_schema | True | True | False/False | False | False | True | 0 | 0 | 0 | True |
| pure_meta_list_schemas | True | True | False/False | False | False | True | 0 | 0 | 0 | True |
| ambiguous_user_schemas | True | True | False/False | False | False | True | 1 | 0 | 3 | True |
| local_schema_count | True | True | False/False | False | False | True | 1 | 0 | 1 | True |
| birthday_message_published | True | True | False/False | False | False | True | 1 | 1 | 1 | True |
| mixed_inactive_journeys | None | None | None/None | None | None | True | 1 | 1 | 2 | True |
| compare_local_live_birthday_status | None | None | None/None | None | None | True | 1 | 1 | 1 | True |
