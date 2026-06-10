# Post-Permission Live API Verification

Diagnostic-only verification after Adobe org/sandbox/permission access changes.

- Credential ready: `False`
- Sandbox ready: `False`
- Token acquisition OK: `False`
- Live success count: `0`
- Live empty count: `0`
- Auth error count: `0`
- Sandbox issue count: `0`
- Endpoint path issue count: `0`
- External unavailable count: `0`
- Usable live API evidence count: `0`
- API state/caveat forwarded count: `0`
- Guard decision: `allowed_not_live_mode`
- Reason: `not_live_mode`
- Full live eval allowed: `False`
- Full generated prompt suite allowed: `False`
- Recommended next command: `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get`
- Recommended follow-up commands: `['python3 scripts/run_live_api_endpoint_path_diagnosis.py']`

## Subcommands

- `python3 scripts/check_adobe_env_local.py` -> `passed` exit=`0` duration=`0.5416`s
- `python3 scripts/audit_live_adobe_api_readiness.py` -> `passed` exit=`0` duration=`0.5241`s
- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get` -> `passed` exit=`0` duration=`0.557`s
- `python3 scripts/run_live_api_evidence_pipeline_trial.py` -> `passed` exit=`0` duration=`0.534`s
- `python3 scripts/run_live_api_targeted_failure_analysis.py` -> `passed` exit=`0` duration=`0.4854`s
