# API Required Readiness Matrix

Infrastructure validation only; this report is not official strict-score evidence.

- Public/dev SQL_FIRST_API_VERIFY rows: `35`
- API_REQUIRED/API_ONLY rows: `28`
- Endpoints needed: `19`
- Discovery chains needed: `4`
- Parser gaps: `0`
- EvidenceBus gaps: `0`
- Answer-slot gaps: `0`
- Live credential blockers: `34`

## Highest-Priority Endpoint Families

- `journey_list`: `3`
- `flowservice_flows`: `3`
- `unified_tags`: `3`
- `merge_policies`: `3`
- `segment_definitions`: `3`
- `segment_jobs`: `3`
- `catalog_datasets`: `2`
- `schemas_short`: `2`

## Rows

- `example_000` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`journey_list`
- `example_001` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`journey_list`
- `example_002` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`journey_list`
- `example_003` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`ups_audiences, flowservice_flows`
- `example_004` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`flowservice_flows`
- `example_005` mode=`API_OPTIONAL` status=`ready_for_live_get` endpoints=`flowservice_flows`
- `example_006` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`catalog_datasets`
- `example_007` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`catalog_datasets`
- `example_008` mode=`SQL_ONLY` status=`ready_sql_only` endpoints=`none`
- `example_009` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`schemas_short`
- `example_010` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`schema_registry_schemas`
- `example_011` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`schemas_short`
- `example_012` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`audit_events`
- `example_013` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`audit_events_short`
- `example_014` mode=`API_REQUIRED` status=`needs_live_credentials` endpoints=`audit_events`
- `example_015` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`unified_tags`
- `example_016` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`unified_tags`
- `example_017` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`unified_tag_categories, unified_tags`
- `example_018` mode=`API_ONLY` status=`needs_discovery_chain` endpoints=`unified_tag_detail`
- `example_019` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`merge_policies`
- `example_020` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`merge_policies`
- `example_021` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`merge_policies`
- `example_022` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_definitions`
- `example_023` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_definitions`
- `example_024` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_definitions`
- `example_025` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_jobs`
- `example_026` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_jobs`
- `example_027` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`segment_jobs`
- `example_028` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`catalog_batches`
- `example_029` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`catalog_batches`
- `example_030` mode=`API_ONLY` status=`needs_discovery_chain` endpoints=`catalog_batch_detail`
- `example_031` mode=`API_ONLY` status=`needs_discovery_chain` endpoints=`export_batch_files`
- `example_032` mode=`API_ONLY` status=`needs_discovery_chain` endpoints=`export_batch_failed`
- `example_033` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`observability_metrics`
- `example_034` mode=`API_ONLY` status=`needs_live_credentials` endpoints=`observability_metrics`
