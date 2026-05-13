# Live API Endpoint Path Diagnosis

Diagnostic-only safe GET endpoint path probe report. No mutating Adobe API calls are used.

- Rows: `4`
- Recommendation: `no_endpoint_catalog_change_without_successful_safe_get_probe`

## Endpoint Rows

- `catalog_datasets` current=`endpoint_path_issue` best=`/data/foundation/catalog/datasets` action=`no_code_fix` code_change=`False`
- `unified_tags` current=`endpoint_path_issue` best=`/data/foundation/unifiedtags/tags` action=`no_code_fix` code_change=`False`
- `catalog_batches` current=`endpoint_path_issue` best=`/data/foundation/catalog/batch` action=`no_code_fix` code_change=`False`
- `schemas_short` current=`endpoint_path_issue` best=`/data/foundation/schemaregistry/tenant/schemas` action=`verify_sandbox` code_change=`False`
