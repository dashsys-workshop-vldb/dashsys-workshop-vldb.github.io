# Schema Registry Safe GET Trial Plan

Diagnostic-only plan for the Schema Registry safe GET request-shape trial.

## Official Request Shape
- Recommended list `Accept`: `application/vnd.adobe.xed-id+json`
- Alternative full-list `Accept`: `application/vnd.adobe.xed+json`
- Tenant list path: `/data/foundation/schemaregistry/tenant/schemas`
- Global list path: `/data/foundation/schemaregistry/global/schemas`

## Current Endpoint Structures

| endpoint_id | family | method | path | params | safe_header_names | accept_present | latest_status | latest_outcome | path_scope |
|---|---|---|---|---|---|---|---:|---|---|
| `schema_registry_schemas` | `schema_registry` | `GET` | `/data/foundation/schemaregistry/tenant/schemas` | `{'limit': 25}` | `[]` | `False` | 400 | `api_error` | `tenant` |
| `schemas_short` | `schema_registry` | `GET` | `/schemas` | `{'limit': 25}` | `[]` | `False` | 404 | `endpoint_path_issue` | `short` |
