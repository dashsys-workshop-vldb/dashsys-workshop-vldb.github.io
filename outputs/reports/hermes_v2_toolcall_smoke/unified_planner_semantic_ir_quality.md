# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `False`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `2`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a formal definition or blueprint that describes the structure, format, data types, and constraints of a data object, message, or record. It defines what fields exist, t |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to produce or display an enumeration of items. It instructs the system to retrieve and show the actual records or names of th |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 0 | 1 | 0 | 0 | 1 | 1 | 1 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | False | There are 0 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 0 | 0 | 1 | 1 | 1 | False | False | Local snapshot evidence shows local_birthday_message_status/SQL/LOCAL_SNAPSHOT: count: 0. Live API evidence was unavailable, so a live comparison cannot be completed. |
