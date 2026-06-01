# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `True`
- atomic_protocol_fallback_used_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- ready_to_run_dev_eval: `True`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a definition or blueprint that describes the structure, format, and constraints of data, such as field names, data types, and relationships, ensuring data consistency a |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" means to enumerate, display, or provide a catalog of the available schemas. It is a request for a collection or inventory of items rather than  |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 0 | 0 | 0 | False | True | Based on the local snapshot, there are 74 schemas. The first five are: Adhoc XDM Schema for dataset JOJourneyVersionsDs_e0f2475b-1232-425e-869d-22e671494d5c, Adhoc XDM Schema for d |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | There are 74 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 1 | 1 | 1 | 0 | 0 | 0 | False | True | The campaign "Birthday Message" was published on 2026-03-31T06:07:32.838462639Z. This timestamp is derived from the local snapshot, as the live API evidence was unavailable due to  |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 1 | 2 | 2 | 0 | 0 | 0 | False | True | Based on the local snapshot, there are 2 inactive journeys: Birthday Message (ID: 9f4ebca4-2fdd-4873-95f5-8d66bab358c6) and Gold Tier Welcome Email (ID: 3f277603-ac4d-4022-a993-8cb |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 1 | 1 | 0 | 0 | 0 | False | True | The local status for the campaign named Birthday Message (ID 9f4ebca4-2fdd-4873-95f5-8d66bab358c6) is updated, with the last update recorded on 2026-03-31T06:07:32.838462639Z. Live |
