# Live API Safe GET Endpoint Matrix

Diagnostic-only safe GET matrix for current normal runtime Adobe credentials.

## Totals

- total_safe_get_endpoints_attempted: `15`
- live_success_count: `10`
- live_empty_count: `5`
- auth_error_count: `0`
- sandbox_scope_issue_count: `0`
- endpoint_path_issue_count: `0`
- external_api_unavailable_count: `0`
- malformed_response_count: `0`
- api_error_count: `0`
- usable_live_payload_endpoint_count: `10`

## Previously Failing Endpoints

- `audit_events_short`: `200` / `live_empty` (`safely_aliased_to_proven_canonical_endpoint`)
- `unified_tags`: `200` / `live_success` (`fixed_with_proven_live_request_shape`)
- `unified_tag_categories`: `200` / `live_success` (`fixed_with_proven_live_request_shape`)

## Endpoints

- `journey_list` GET `/ajo/journey` status=`200` outcome=`live_empty` parser=`pass` usable_payload=`False`
- `ups_audiences` GET `/data/core/ups/audiences` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `segment_definitions` GET `/data/core/ups/segment/definitions` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `flowservice_flows` GET `/data/foundation/flowservice/flows` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `flowservice_runs` GET `/data/foundation/flowservice/runs` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `catalog_datasets` GET `/data/foundation/catalog/dataSets` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` status=`200` outcome=`live_empty` parser=`pass` usable_payload=`False`
- `unified_tags` GET `https://experience.adobe.io/unifiedtags/tags` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `merge_policies` GET `/data/core/ups/config/mergePolicies` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `catalog_batches` GET `/data/foundation/catalog/batches` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `audit_events` GET `/data/foundation/audit/events` status=`200` outcome=`live_empty` parser=`pass` usable_payload=`False`
- `schemas_short` GET `/data/foundation/schemaregistry/tenant/schemas` status=`200` outcome=`live_empty` parser=`pass` usable_payload=`False`
- `audit_events_short` GET `/data/foundation/audit/events` status=`200` outcome=`live_empty` parser=`pass` usable_payload=`False`
- `unified_tag_categories` GET `https://experience.adobe.io/unifiedtags/tagCategory` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
- `segment_jobs` GET `/data/core/ups/segment/jobs` status=`200` outcome=`live_success` parser=`pass` usable_payload=`True`
