# Post-Permission Live API Verification

Diagnostic-only verification after Adobe org/sandbox/permission access changes.

- Credential ready: `True`
- Sandbox ready: `True`
- Token acquisition OK: `True`
- Live success count: `0`
- Live empty count: `0`
- Auth error count: `3`
- Sandbox issue count: `5`
- Endpoint path issue count: `6`
- External unavailable count: `1`
- Usable live API evidence count: `0`
- API state/caveat forwarded count: `10`
- Guard decision: `blocked`
- Reason: `no_live_success`
- Full live eval allowed: `False`
- Full generated prompt suite allowed: `False`
- Recommended next command: `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get`
- Recommended follow-up commands: `['python3 scripts/run_live_api_readiness_smoke.py --endpoint-id ups_audiences', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_definitions', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id merge_policies', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_flows', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_runs', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schema_registry_schemas', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_jobs', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_datasets', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tags', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_batches', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schemas_short', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events_short', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tag_categories', 'python3 scripts/run_live_api_readiness_smoke.py --endpoint-id journey_list', 'python3 scripts/run_live_api_endpoint_path_diagnosis.py']`

## Subcommands

- `python3 scripts/check_adobe_env_local.py` -> `passed` exit=`0` duration=`0.3419`s
- `python3 scripts/audit_live_adobe_api_readiness.py` -> `passed` exit=`0` duration=`2.2539`s
- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get` -> `passed` exit=`0` duration=`22.2582`s
- `python3 scripts/run_live_api_evidence_pipeline_trial.py` -> `passed` exit=`0` duration=`23.596`s
- `python3 scripts/run_live_api_targeted_failure_analysis.py` -> `passed` exit=`0` duration=`0.4695`s
