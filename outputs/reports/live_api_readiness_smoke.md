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
- Failure count: `1`
- Auth failures: `0`
- Rate limits: `0`
- Response parser status: `pass`
- EvidenceBus forwarding status: `pass`
- Answer synthesis status: `pass`
- Residual risk: GET smoke checks verify connectivity and parsing only; they do not claim official strict-score improvement.

## Endpoints Tested

- `ups_audiences` GET `/data/core/ups/audiences` outcome=`external_api_unavailable` ok=`False` status=`500` parser=`pass`

## Skipped Endpoints

- `journey_list` GET `/ajo/journey` reason=`not_matching_filter`
- `segment_definitions` GET `/data/core/ups/segment/definitions` reason=`not_matching_filter`
- `flowservice_flows` GET `/data/foundation/flowservice/flows` reason=`not_matching_filter`
- `flowservice_runs` GET `/data/foundation/flowservice/runs` reason=`not_matching_filter`
- `catalog_datasets` GET `/data/foundation/catalog/dataSets` reason=`not_matching_filter`
- `schema_registry_schema` GET `/data/foundation/schemaregistry/tenant/schemas/{schema_id}` reason=`requires_discovery_chain_or_path_param`
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` reason=`not_matching_filter`
- `schemas_short` GET `/schemas` reason=`not_matching_filter`
- `audit_events` GET `/data/foundation/audit/events` reason=`not_matching_filter`
- `audit_events_short` GET `/audit/events` reason=`not_matching_filter`
- `unified_tags` GET `/unifiedtags/tags` reason=`not_matching_filter`
- `unified_tag_categories` GET `/unifiedtags/tagCategory` reason=`not_matching_filter`
- `unified_tag_detail` GET `/unifiedtags/tags/{tag_id}` reason=`requires_discovery_chain_or_path_param`
- `merge_policies` GET `/data/core/ups/config/mergePolicies` reason=`not_matching_filter`
- `segment_jobs` GET `/data/core/ups/segment/jobs` reason=`not_matching_filter`
- `catalog_batches` GET `/data/foundation/catalog/batches` reason=`not_matching_filter`
- `catalog_batch_detail` GET `/data/foundation/catalog/batches/{batch_id}` reason=`requires_discovery_chain_or_path_param`
- `export_batch_files` GET `/data/foundation/export/batches/{batch_id}/files` reason=`requires_discovery_chain_or_path_param`
- `export_batch_failed` GET `/data/foundation/export/batches/{batch_id}/failed` reason=`requires_discovery_chain_or_path_param`
- `observability_metrics` POST `/data/infrastructure/observability/insights/metrics` reason=`non_get_endpoint`
