# Live API Endpoint Follow-Up Commands

Diagnostic-only safe rerun commands. No credentials are included.

## Endpoint Commands

- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id ups_audiences` - action: `verify_permission`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_definitions` - action: `verify_permission`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id merge_policies` - action: `verify_permission`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_flows` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_runs` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schema_registry_schemas` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_datasets` - action: `no_code_fix`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tags` - action: `no_code_fix`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_batches` - action: `no_code_fix`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schemas_short` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id journey_list` - action: `wait_external_service`

## Family Commands

- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family flowservice` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family catalog` - action: `no_code_fix`
- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get` - action: `rerun_with_endpoint_filter`
- `python3 scripts/run_live_api_endpoint_path_diagnosis.py` - action: `no_code_fix`
