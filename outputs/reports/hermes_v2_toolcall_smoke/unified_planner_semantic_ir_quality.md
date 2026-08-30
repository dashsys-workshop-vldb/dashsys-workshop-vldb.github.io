# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `False`
- free_form_sql_api_avoided: `False`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `4`
- unsupported_claims: `0`
- no_tool_fp: `5`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a blueprint or definition that describes the structure, format, and data types of a dataset or record. In the context of Adobe Experience Platform, a schema (often call |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | In the phrase "list schemas," the verb "list" means to display, enumerate, or provide a comprehensive catalog of all available schemas. |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
| local_schema_count | EVIDENCE_SQL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
| birthday_message_published | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
