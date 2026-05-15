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
- Failure count: `15`
- Auth failures: `3`
- Rate limits: `0`
- Response parser status: `pass`
- EvidenceBus forwarding status: `pass`
- Answer synthesis status: `pass`
- Residual risk: GET smoke checks verify connectivity and parsing only; they do not claim official strict-score improvement.

## Endpoints Tested

- `journey_list` GET `/ajo/journey` outcome=`external_api_unavailable` ok=`False` status=`500` parser=`pass`
- `ups_audiences` GET `/data/core/ups/audiences` outcome=`auth_error` ok=`False` status=`401` parser=`pass`
- `segment_definitions` GET `/data/core/ups/segment/definitions` outcome=`auth_error` ok=`False` status=`401` parser=`pass`
- `flowservice_flows` GET `/data/foundation/flowservice/flows` outcome=`sandbox_scope_issue` ok=`False` status=`500` parser=`pass`
- `flowservice_runs` GET `/data/foundation/flowservice/runs` outcome=`sandbox_scope_issue` ok=`False` status=`500` parser=`pass`
- `catalog_datasets` GET `/data/foundation/catalog/dataSets` outcome=`endpoint_path_issue` ok=`False` status=`500` parser=`pass`
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` outcome=`sandbox_scope_issue` ok=`False` status=`500` parser=`pass`
- `unified_tags` GET `/unifiedtags/tags` outcome=`endpoint_path_issue` ok=`False` status=`404` parser=`pass`
- `merge_policies` GET `/data/core/ups/config/mergePolicies` outcome=`auth_error` ok=`False` status=`401` parser=`pass`
- `catalog_batches` GET `/data/foundation/catalog/batches` outcome=`endpoint_path_issue` ok=`False` status=`500` parser=`pass`
- `audit_events` GET `/data/foundation/audit/events` outcome=`sandbox_scope_issue` ok=`False` status=`400` parser=`pass`
- `schemas_short` GET `/schemas` outcome=`endpoint_path_issue` ok=`False` status=`404` parser=`pass`
- `audit_events_short` GET `/audit/events` outcome=`endpoint_path_issue` ok=`False` status=`404` parser=`pass`
- `unified_tag_categories` GET `/unifiedtags/tagCategory` outcome=`endpoint_path_issue` ok=`False` status=`404` parser=`pass`
- `segment_jobs` GET `/data/core/ups/segment/jobs` outcome=`sandbox_scope_issue` ok=`False` status=`400` parser=`pass`

## Skipped Endpoints

- `schema_registry_schema` GET `/data/foundation/schemaregistry/tenant/schemas/{schema_id}` reason=`requires_discovery_chain_or_path_param`
- `unified_tag_detail` GET `/unifiedtags/tags/{tag_id}` reason=`requires_discovery_chain_or_path_param`
- `catalog_batch_detail` GET `/data/foundation/catalog/batches/{batch_id}` reason=`requires_discovery_chain_or_path_param`
- `export_batch_files` GET `/data/foundation/export/batches/{batch_id}/files` reason=`requires_discovery_chain_or_path_param`
- `export_batch_failed` GET `/data/foundation/export/batches/{batch_id}/failed` reason=`requires_discovery_chain_or_path_param`
- `observability_metrics` POST `/data/infrastructure/observability/insights/metrics` reason=`non_get_endpoint`
