# Pure LLM Tool-Choice Root Cause Audit

Diagnostic-only audit for shadow Pure LLM evidence-source selection. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

- Rows audited: `5`

## Root Causes
- `endpoint_catalog_overselected`: `1`
- `prompt_intent_misread`: `3`
- `sql_plan_failed_after_correct_tool`: `1`

## Rows
### example_000 / `api_only_only_when_sql_unavailable_v1`
- Prompt: When was the journey 'Birthday Message' published?
- Selected evidence source: `execute_sql`
- Should have considered: `local_sql_required`
- Root cause: `sql_plan_failed_after_correct_tool`
- Relevant SQL tables: `['dim_campaign', 'dim_connector', 'dim_blueprint', 'dim_collection', 'dim_segment']`
- Relevant API endpoints: `['journey_list', 'schema_registry_schema', 'unified_tag_detail']`

### example_001 / `api_only_only_when_sql_unavailable_v1`
- Prompt: Give me inactive journeys
- Selected evidence source: `execute_sql`
- Should have considered: `local_sql_required`
- Root cause: `prompt_intent_misread`
- Relevant SQL tables: `['dim_campaign', 'dim_connector', 'dim_blueprint', 'dim_collection', 'dim_segment']`
- Relevant API endpoints: `['journey_list']`

### example_002 / `api_only_only_when_sql_unavailable_v1`
- Prompt: List all journeys
- Selected evidence source: `execute_sql`
- Should have considered: `local_sql_required`
- Root cause: `prompt_intent_misread`
- Relevant SQL tables: `['dim_campaign', 'dim_connector', 'dim_blueprint', 'dim_collection', 'dim_segment']`
- Relevant API endpoints: `['journey_list', 'catalog_batches', 'catalog_datasets', 'export_batch_failed', 'export_batch_files']`

### example_003 / `api_only_only_when_sql_unavailable_v1`
- Prompt: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- Selected evidence source: `execute_sql`
- Should have considered: `local_sql_required`
- Root cause: `prompt_intent_misread`
- Relevant SQL tables: `['dim_segment', 'dim_target', 'hkg_br_base_segment_used_by_dependent_segment', 'dim_campaign', 'dim_connector']`
- Relevant API endpoints: `['ups_audiences', 'merge_policies', 'segment_jobs', 'export_batch_files', 'flowservice_flows']`

### example_004 / `api_only_only_when_sql_unavailable_v1`
- Prompt: Show me the IDs of failed dataflow runs
- Selected evidence source: `call_api`
- Should have considered: `mixed_sql_api`
- Root cause: `endpoint_catalog_overselected`
- Relevant SQL tables: `['dim_campaign', 'dim_connector', 'dim_blueprint', 'dim_collection', 'dim_segment']`
- Relevant API endpoints: `['flowservice_runs', 'audit_events', 'export_batch_failed', 'flowservice_flows']`
