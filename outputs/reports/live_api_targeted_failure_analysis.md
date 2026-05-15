# Live API Targeted Failure Analysis

Diagnostic-only analysis using the shared API outcome classifier.

## Failure Counts

- `api_error`: `10`
- `auth_error`: `3`
- `endpoint_path_issue`: `6`
- `external_api_unavailable`: `1`
- `sandbox_scope_issue`: `5`

## Next Actions

- `journey_list` failure=`external_api_unavailable` next_action=`wait_external_service` code_fix_allowed=`False` reason=`adobe_service_or_server_issue`
- `ups_audiences` failure=`auth_error` next_action=`verify_permission` code_fix_allowed=`False` reason=`adobe_permission_or_scope_setup`
- `segment_definitions` failure=`auth_error` next_action=`verify_permission` code_fix_allowed=`False` reason=`adobe_permission_or_scope_setup`
- `flowservice_flows` failure=`sandbox_scope_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`adobe_sandbox_or_environment_setup`
- `flowservice_runs` failure=`sandbox_scope_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`adobe_sandbox_or_environment_setup`
- `catalog_datasets` failure=`endpoint_path_issue` next_action=`no_code_fix` code_fix_allowed=`False` reason=`no_successful_safe_get_candidate`
- `schema_registry_schemas` failure=`sandbox_scope_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`adobe_sandbox_or_environment_setup`
- `unified_tags` failure=`endpoint_path_issue` next_action=`no_code_fix` code_fix_allowed=`False` reason=`no_successful_safe_get_candidate`
- `merge_policies` failure=`auth_error` next_action=`verify_permission` code_fix_allowed=`False` reason=`adobe_permission_or_scope_setup`
- `catalog_batches` failure=`endpoint_path_issue` next_action=`no_code_fix` code_fix_allowed=`False` reason=`no_successful_safe_get_candidate`
- `audit_events` failure=`sandbox_scope_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`adobe_sandbox_or_environment_setup`
- `schemas_short` failure=`endpoint_path_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`no_successful_safe_get_candidate`
- `audit_events_short` failure=`endpoint_path_issue` next_action=`rerun_with_endpoint_filter` code_fix_allowed=`False` reason=`endpoint_path_unverified`
- `unified_tag_categories` failure=`endpoint_path_issue` next_action=`rerun_with_endpoint_filter` code_fix_allowed=`False` reason=`endpoint_path_unverified`
- `segment_jobs` failure=`sandbox_scope_issue` next_action=`verify_sandbox` code_fix_allowed=`False` reason=`adobe_sandbox_or_environment_setup`
- `example_000` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_001` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_002` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_003` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_003` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_004` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_005` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_006` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_007` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
- `example_009` failure=`api_error` next_action=`inspect_redacted_error_shape` code_fix_allowed=`False` reason=`api_error_state_only`
