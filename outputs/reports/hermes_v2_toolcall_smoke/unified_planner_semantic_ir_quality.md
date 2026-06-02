# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `True`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a definition or blueprint that describes the structure, format, and rules for data. In the context of Adobe Experience Platform, a schema defines the fields, data types |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to display, enumerate, or provide a catalog of schema records. It indicates an action to retrieve and show multiple schema en |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 0 | 0 | 0 | False | True | The local snapshot contains 74 schemas. The first five retrieved are:  1. Adhoc XDM Schema for dataset JOJourneyVersionsDs_e0f2475b-1232-425e-869d-22e671494d5c (ID: 8f2838c4eb4311b |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | There are 74 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 0 | 1 | 1 | 1 | 1 | 1 | False | False | I found runtime evidence but could not compose a verified final answer. Available scoped evidence includes: t1_lookup_journey_id/SQL/LOCAL_SNAPSHOT: CAMPAIGNID:9f4ebca4-2fdd-4873-9 |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 1 | 2 | 2 | 1 | 1 | 1 | False | False | I found runtime evidence but could not compose a verified final answer. Available scoped evidence includes: t2_list_inactive_journeys/SQL/LOCAL_SNAPSHOT: CAMPAIGNID:9f4ebca4-2fdd-4 |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 1 | 1 | 0 | 0 | 0 | False | True | The local snapshot for the campaign named Birthday Message (ID 9f4ebca4-2fdd-4873-95f5-8d66bab358c6) shows a status of updated. Live API evidence was unavailable due to Adobe crede |
