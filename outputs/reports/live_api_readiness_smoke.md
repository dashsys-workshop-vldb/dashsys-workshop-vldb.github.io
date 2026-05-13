# Live API Readiness Smoke

Infrastructure validation only; this report is not official strict-score evidence.

- Status: `complete`
- Credentials present: `True`
- Live mode attempted: `True`
- Dry-run fallback verified: `False`
- Credential ready: `True`
- Sandbox ready: `True`
- Ready for live smoke: `True`
- Ready for sandbox endpoints: `True`
- Success count: `0`
- Failure count: `5`
- Auth failures: `2`
- Rate limits: `0`
- Response parser status: `pass`
- EvidenceBus forwarding status: `pass`
- Answer synthesis status: `pass`
- Residual risk: GET smoke checks verify connectivity and parsing only; they do not claim official strict-score improvement.

## Endpoints Tested

- `journey_list` GET `/ajo/journey` outcome=`external_api_unavailable` ok=`False` status=`500` parser=`pass`
- `ups_audiences` GET `/data/core/ups/audiences` outcome=`auth_error` ok=`False` status=`401` parser=`pass`
- `segment_definitions` GET `/data/core/ups/segment/definitions` outcome=`auth_error` ok=`False` status=`401` parser=`pass`
- `flowservice_flows` GET `/data/foundation/flowservice/flows` outcome=`external_api_unavailable` ok=`False` status=`500` parser=`pass`
- `flowservice_runs` GET `/data/foundation/flowservice/runs` outcome=`external_api_unavailable` ok=`False` status=`500` parser=`pass`

## Skipped Endpoints

- `catalog_datasets` GET `/data/foundation/catalog/dataSets` reason=`not_selected_by_limit`
- `schema_registry_schema` GET `/data/foundation/schemaregistry/tenant/schemas/{schema_id}` reason=`requires_discovery_chain_or_path_param`
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` reason=`not_selected_by_limit`
- `schemas_short` GET `/schemas` reason=`not_selected_by_limit`
- `audit_events` GET `/data/foundation/audit/events` reason=`not_selected_by_limit`
- `audit_events_short` GET `/audit/events` reason=`not_selected_by_limit`
- `unified_tags` GET `/unifiedtags/tags` reason=`not_selected_by_limit`
- `unified_tag_categories` GET `/unifiedtags/tagCategory` reason=`not_selected_by_limit`
- `unified_tag_detail` GET `/unifiedtags/tags/{tag_id}` reason=`requires_discovery_chain_or_path_param`
- `merge_policies` GET `/data/core/ups/config/mergePolicies` reason=`not_selected_by_limit`
- `segment_jobs` GET `/data/core/ups/segment/jobs` reason=`not_selected_by_limit`
- `catalog_batches` GET `/data/foundation/catalog/batches` reason=`not_selected_by_limit`
- `catalog_batch_detail` GET `/data/foundation/catalog/batches/{batch_id}` reason=`requires_discovery_chain_or_path_param`
- `export_batch_files` GET `/data/foundation/export/batches/{batch_id}/files` reason=`requires_discovery_chain_or_path_param`
- `export_batch_failed` GET `/data/foundation/export/batches/{batch_id}/failed` reason=`requires_discovery_chain_or_path_param`
- `observability_metrics` POST `/data/infrastructure/observability/insights/metrics` reason=`non_get_endpoint`
