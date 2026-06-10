# Live API Full Run Guard

- Guard decision: `allowed_full_live_diagnostic_eval`
- Reason: `all_runtime_selectable_safe_get_endpoint_path_failures_resolved_and_guarded_live_e2e_passed`
- Live success count: `10`
- Failure counts: `{}`
- Go/no-go recommendation: `GO_FOR_FULL_LIVE_DIAGNOSTIC_EVAL`
- Live strict eval run in this pass: `True`
- 250-prompt diagnostics run in this pass: `False`

## Strict Eval Result

- Best overall: `SQL_FIRST_API_VERIFY`
- SQL_FIRST_API_VERIFY final score: `0.6247`

## Safe Rerun Commands

- `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get`
- `python3 scripts/run_guarded_dash_agent_live_e2e_trial.py`
- `python3 scripts/run_dev_eval.py --strict`
