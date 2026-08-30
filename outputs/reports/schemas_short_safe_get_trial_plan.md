# schemas_short Safe GET Trial Plan

- Diagnostic only: `true`
- Official score claim: `false`
- Normal runtime env source: `.env.local`
- Docs basis: Schema Registry list GET requires `Accept`; tenant/global list paths are the canonical Schema Registry list shapes.

## Endpoint Inspection

### schema_registry_schemas
- family: `schema_list`
- semantic purpose: Canonical tenant Schema Registry list endpoint already proven with endpoint-specific Accept header.
- method: `GET`
- path: `/data/foundation/schemaregistry/tenant/schemas`
- params: `{"limit": 25}`
- header names: `['Accept']`
- Accept present: `True`
- intended operation: `tenant schema list`
- latest baseline: `200` / `live_empty`
- path scope: `tenant`

### schemas_short
- family: `schema_list`
- semantic purpose: Gold-example shorthand for schema list/name lookup; no path parameters and no schema ID requirement in catalog.
- method: `GET`
- path: `/schemas`
- params: `{"limit": 25}`
- header names: `[]`
- Accept present: `False`
- intended operation: `shorthand alias for schema list/name lookup`
- latest baseline: `404` / `endpoint_path_issue`
- path scope: `short`

## Semantics Decision
- schemas_short_is_schema_list_alias: `True`
- schemas_short_is_single_schema_lookup: `False`
- safe_to_run_list_variants: `True`
