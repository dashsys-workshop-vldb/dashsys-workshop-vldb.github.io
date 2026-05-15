# Live API Full Run Blocker

Large live API diagnostics are blocked until smoke evidence is trustworthy or an explicit diagnostic override is used.

- Created at: `2026-05-15T18:06:52.315031+00:00`
- Guard decision: `blocked`
- Reason: `no_live_success`
- Live success count: `0`
- Failure counts: `{'external_api_unavailable': 1, 'auth_error': 3, 'sandbox_scope_issue': 5, 'endpoint_path_issue': 6}`
- Override flag: `--allow-live-diagnostic-without-success`

## Safe Rerun Commands

- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events_short`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_batches`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_datasets`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_flows`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_runs`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id journey_list`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id merge_policies`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schema_registry_schemas`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schemas_short`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_definitions`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_jobs`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tag_categories`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tags`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id ups_audiences`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family audit`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family catalog`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family flowservice`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family journey`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-family schema`
- `python3 scripts/run_live_api_endpoint_path_diagnosis.py`
