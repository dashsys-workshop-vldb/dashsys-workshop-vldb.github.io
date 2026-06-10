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
- Success count: `15`
- Failure count: `0`
- Auth failures: `0`
- Rate limits: `0`
- Response parser status: `pass`
- EvidenceBus forwarding status: `pass`
- Answer synthesis status: `pass`
- Residual risk: GET smoke checks verify connectivity and parsing only; they do not claim official strict-score improvement.

## Endpoints Tested

- `journey_list` GET `/ajo/journey` outcome=`live_empty` ok=`True` status=`200` parser=`pass`
- `ups_audiences` GET `/data/core/ups/audiences` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `segment_definitions` GET `/data/core/ups/segment/definitions` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `flowservice_flows` GET `/data/foundation/flowservice/flows` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `flowservice_runs` GET `/data/foundation/flowservice/runs` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `catalog_datasets` GET `/data/foundation/catalog/dataSets` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` outcome=`live_empty` ok=`True` status=`200` parser=`pass`
- `unified_tags` GET `https://experience.adobe.io/unifiedtags/tags` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `merge_policies` GET `/data/core/ups/config/mergePolicies` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `catalog_batches` GET `/data/foundation/catalog/batches` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `audit_events` GET `/data/foundation/audit/events` outcome=`live_empty` ok=`True` status=`200` parser=`pass`
- `schemas_short` GET `/data/foundation/schemaregistry/tenant/schemas` outcome=`live_empty` ok=`True` status=`200` parser=`pass`
- `audit_events_short` GET `/data/foundation/audit/events` outcome=`live_empty` ok=`True` status=`200` parser=`pass`
- `unified_tag_categories` GET `https://experience.adobe.io/unifiedtags/tagCategory` outcome=`live_success` ok=`True` status=`200` parser=`pass`
- `segment_jobs` GET `/data/core/ups/segment/jobs` outcome=`live_success` ok=`True` status=`200` parser=`pass`

## Skipped Endpoints

- `schema_registry_schema` GET `/data/foundation/schemaregistry/tenant/schemas/{schema_id}` reason=`requires_discovery_chain_or_path_param`
- `unified_tag_detail` GET `https://experience.adobe.io/unifiedtags/tags/{tag_id}` reason=`requires_discovery_chain_or_path_param`
- `catalog_batch_detail` GET `/data/foundation/catalog/batches/{batch_id}` reason=`requires_discovery_chain_or_path_param`
- `export_batch_files` GET `/data/foundation/export/batches/{batch_id}/files` reason=`requires_discovery_chain_or_path_param`
- `export_batch_failed` GET `/data/foundation/export/batches/{batch_id}/failed` reason=`requires_discovery_chain_or_path_param`
- `observability_metrics` POST `/data/infrastructure/observability/insights/metrics` reason=`non_get_endpoint`
