# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `True`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- ready_to_run_dev_eval: `True`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a structured definition or blueprint that describes the format, fields, data types, and relationships of data. In the context of data platforms like Adobe Experience Pl |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to display, enumerate, or provide a catalog of schema records. It indicates an action to retrieve and show multiple schema en |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 1 | 0 | 1 | False | True | Local snapshot evidence shows t1_local_schemas/SQL/LOCAL_SNAPSHOT: count: 50; examples include Adhoc XDM Schema for dataset JOJourneyVersionsDs_e0f2475b-1232-425e-869d-22e671494d5c |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | There are 74 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | The journey "Birthday Message" was created and updated on 2026-03-31T06:07:32.838462639Z. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 0 | 2 | 2 | 1 | 0 | 1 | False | True | Local snapshot evidence shows t2_list_inactive_journeys_local/SQL/LOCAL_SNAPSHOT: count: 2; examples include Birthday Message; Gold Tier Welcome Email; id: 9f4ebca4-2fdd-4873-95f5- |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 1 | 1 | 0 | 0 | 0 | False | True | For the campaign named Birthday Message, the local snapshot status is updated. Live API evidence was unavailable due to Adobe credentials being unavailable, so the live status coul |
