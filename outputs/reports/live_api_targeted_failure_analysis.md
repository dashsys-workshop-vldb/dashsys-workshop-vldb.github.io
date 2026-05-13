# Live API Targeted Failure Analysis

Diagnostic-only analysis using the shared API outcome classifier.

## Failure Counts

- `api_error`: `10`
- `auth_error`: `3`
- `endpoint_path_issue`: `4`
- `external_api_unavailable`: `1`
- `sandbox_scope_issue`: `4`

## Next Actions

- `journey_list` failure=`external_api_unavailable` next_action=`wait_external_service`
- `ups_audiences` failure=`auth_error` next_action=`verify_permission`
- `segment_definitions` failure=`auth_error` next_action=`verify_permission`
- `flowservice_flows` failure=`sandbox_scope_issue` next_action=`verify_sandbox`
- `flowservice_runs` failure=`sandbox_scope_issue` next_action=`verify_sandbox`
- `catalog_datasets` failure=`endpoint_path_issue` next_action=`fix_endpoint_path`
- `schema_registry_schemas` failure=`sandbox_scope_issue` next_action=`verify_sandbox`
- `unified_tags` failure=`endpoint_path_issue` next_action=`fix_endpoint_path`
- `merge_policies` failure=`auth_error` next_action=`verify_permission`
- `catalog_batches` failure=`endpoint_path_issue` next_action=`fix_endpoint_path`
- `audit_events` failure=`sandbox_scope_issue` next_action=`verify_sandbox`
- `schemas_short` failure=`endpoint_path_issue` next_action=`fix_endpoint_path`
- `example_000` failure=`api_error` next_action=`no_code_fix`
- `example_001` failure=`api_error` next_action=`no_code_fix`
- `example_002` failure=`api_error` next_action=`no_code_fix`
- `example_003` failure=`api_error` next_action=`no_code_fix`
- `example_003` failure=`api_error` next_action=`no_code_fix`
- `example_004` failure=`api_error` next_action=`no_code_fix`
- `example_005` failure=`api_error` next_action=`no_code_fix`
- `example_006` failure=`api_error` next_action=`no_code_fix`
- `example_007` failure=`api_error` next_action=`no_code_fix`
- `example_009` failure=`api_error` next_action=`no_code_fix`
