# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `True`
- free_form_sql_api_avoided: `False`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a formal definition or blueprint that describes the structure, format, data types, and constraints of data within a system. It defines how data elements are organized,  |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to produce or display an enumeration, catalog, or ordered sequence of items—in this case, the schemas. It instructs the syste |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | No matching runtime evidence was available for this query/scope. |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | False | There are 0 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | No matching runtime evidence was available for this query/scope. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 0 | 0 | 0 | False | True | The concept of an inactive journey could not be verified due to a runtime error. However, the local snapshot identified five inactive journeys, all associated with the client ID ac |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 1 | 1 | 0 | 0 | 1 | 0 | 1 | True | False | The local snapshot for the status returned zero rows, while live API evidence was unavailable due to Adobe credentials not being available. |
