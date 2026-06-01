# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `True`
- atomic_protocol_fallback_used_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- ready_to_run_dev_eval: `False`
- latest_full_smoke_status: `last completed smoke failed; final rerun after final patches was interrupted after the local model hung on mixed_inactive_journeys before writing a fresh report`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | True | A schema is a definition or blueprint that describes the structure, format, and rules for data within a system. It specifies the fields, data types, constraints, and relationships  |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | True | In the phrase "list schemas", "list" means to enumerate, display, or provide a catalog of the available schemas. It is a request for a collection or inventory of schema records rat |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 1 | 3 | 3 | 1 | 1 | False | I could not compose a verified final answer from the available runtime evidence. |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 3 | 3 | 1 | 1 | False | I could not compose a verified final answer from the available runtime evidence. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 1 | 1 | 1 | 1 | 1 | False | I could not compose a verified final answer from the available runtime evidence. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 1 | 2 | 2 | 1 | 1 | False | I could not compose a verified final answer from the available runtime evidence. |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 1 | 1 | 0 | 0 | True | The local status for the 'Birthday Message' campaign (ID: 9f4ebca4-2fdd-4873-95f5-8d66bab358c6) is 'updated', with a last update time of 2026-03-31T06:07:32.838462639Z. However, th |
