# Unified Planner Semantic IR Quality

- unified_planner_facade_restored: `True`
- semantic_ir_primary: `False`
- free_form_sql_api_avoided: `False`
- atomic_protocol_fallback_used_count: `0`
- timeout_count: `1`
- unsupported_claims: `0`
- no_tool_fp: `1`
- ready_to_run_dev_eval: `False`

## Smoke Rows

| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a structured definition or blueprint that describes the format, fields, data types, and relationships of data. In the context of data platforms like Adobe Experience Pl |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to display, enumerate, or provide a catalog of schema records. It indicates an action to retrieve and show a collection of sc |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 0 | 0 | 0 | False | True | The local snapshot contains 50 XDM schemas, all created and updated on 2026-04-15T06:58:17.000+00:00 with no labels or descriptions. Examples include Adhoc XDM Schema for dataset J |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | There are 74 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | The journey named Birthday Message was published on 2026-03-31T06:07:32.838462639Z. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 0 | 2 | 2 | 1 | 0 | 1 | True | True | Based on the local snapshot, there are two journeys: Birthday Message and Gold Tier Welcome Email. The concept of an inactive journey could not be verified due to an error in the d |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | False |  |
