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
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a formal definition or blueprint that describes the structure, format, data types, constraints, and relationships of data within a system, database, or API. It serves a |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to produce or display an enumeration, catalog, or ordered sequence of items—in this case, the schemas. It instructs the syste |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
| local_schema_count | EVIDENCE_SQL | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False | Runtime evidence was unavailable; cannot provide a verified answer. |
