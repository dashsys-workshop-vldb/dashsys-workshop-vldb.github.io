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
| pure_concept_schema | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | A schema is a self-describing, immutable definition of a data structure. It defines the fields, data types, and hierarchy of data records, ensuring consistency and interoperability |
| pure_meta_list_schemas | DIRECT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False | True | In the phrase "list schemas", "list" is a verb meaning to enumerate, display, or provide a catalog of schemas. It indicates an action to retrieve or show a collection of schema rec |
| ambiguous_user_schemas | EVIDENCE_LOCAL | 1 | 0 | 3 | 3 | 1 | 0 | 1 | False | True | Local snapshot evidence shows local_schemas_list/SQL/LOCAL_SNAPSHOT: count: 50; relationship: LABELSBLUEPRINT:[] -> BLUEPRINTID:8f2838c4eb4311be76d64e2684c4895648fb9344cf751bfc (Ad |
| local_schema_count | EVIDENCE_SQL | 1 | 0 | 1 | 1 | 0 | 0 | 0 | False | True | There are 74 schema records in the local snapshot. |
| birthday_message_published | EVIDENCE_LOCAL | 1 | 0 | 1 | 1 | 1 | 0 | 1 | False | True | Local snapshot evidence shows task_journey_published_date/SQL/LOCAL_SNAPSHOT: count: 1; examples include Birthday Message; status: published; NAME:Birthday Message. |
| mixed_inactive_journeys | EVIDENCE_LOCAL | 1 | 0 | 2 | 2 | 0 | 0 | 0 | False | True | An inactive journey refers to a user path or workflow that has been paused, abandoned, or is no longer actively receiving. Based on the local snapshot, there are two such journeys: |
| compare_local_live_birthday_status | EVIDENCE_LIVE_IF_AVAILABLE | 2 | 2 | 1 | 1 | 0 | 0 | 0 | False | True | For the entity named Birthday Message, the local snapshot status is updated. Live API evidence was unavailable or errored for this source, so live status could not be verified. |
