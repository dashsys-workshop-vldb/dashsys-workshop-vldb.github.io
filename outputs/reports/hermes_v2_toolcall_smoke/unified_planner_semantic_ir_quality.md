# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `False`
- free_form_sql_api_avoided: `False`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `2`
- unsupported_claims: `0`
- no_tool_fp: `3`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a formal definition or blueprint that describes the structure, format, and constraints of data. It specifies the fields, data types, relationships, and rules that gover |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to display, enumerate, or provide a catalog of schemas. It indicates an action to retrieve and show a collection of schema re |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | I do not have access to a list of schemas in my current local data snapshot. To see your schemas, you would need to query the Adobe Experience Platform Schema Registry API. |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | False | There are 0 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 0 | 0 | 1 | 0 | 1 | False | False | Local snapshot evidence shows local_birthday_message_status/SQL/LOCAL_SNAPSHOT: count: 0. Live API evidence was unavailable, so a live comparison cannot be completed. |
