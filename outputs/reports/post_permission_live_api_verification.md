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
- Full live eval allowed: `False`
- Full generated prompt suite allowed: `False`
- Recommended next command: `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id ups_audiences`

## Subcommands

- `python3 scripts/check_adobe_env_local.py` -> `passed` exit=`0` duration=`0.3379`s
- `python3 scripts/audit_live_adobe_api_readiness.py` -> `passed` exit=`0` duration=`4.5834`s
- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get` -> `passed` exit=`0` duration=`30.64`s
- `python3 scripts/run_live_api_evidence_pipeline_trial.py` -> `passed` exit=`0` duration=`34.9004`s
- `python3 scripts/run_live_api_targeted_failure_analysis.py` -> `passed` exit=`0` duration=`0.4927`s
