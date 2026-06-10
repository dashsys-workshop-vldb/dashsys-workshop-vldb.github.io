# Live API Endpoint Follow-Up Commands

Diagnostic-only safe rerun commands. No credentials are included.

## Endpoint Commands


## Family Commands

- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family flowservice` - action: `verify_sandbox`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family catalog` - action: `no_code_fix`
- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get` - action: `rerun_with_endpoint_filter`
- `python3 scripts/run_live_api_endpoint_path_diagnosis.py` - action: `no_code_fix`
