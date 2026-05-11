# Live API Evidence Pipeline Trial

Infrastructure validation only; this report does not compute or claim official strict-score improvement.

- Status: `skipped_live_credentials_missing`
- Credentials present: `False`
- Live mode attempted: `False`
- Dry-run fallback verified: `True`
- Total prompts: `1`
- Live API executed count: `0`
- Dry-run fallback count: `1`
- Parser success count: `1`
- EvidenceBus API evidence count: `1`
- Answer used API evidence count: `0`
- Unsupported API claim count: `0`
- Live/dry-run mismatch count: `0`
- Recommendation: `provide_live_credentials_then_rerun`
- Residual risk: Live API execution, real payload parsing, EvidenceBus forwarding from live payloads, and auth/rate-limit handling remain unverified until Adobe credentials are available.

## Prompt Rows

- `dry_run_fallback_probe` live_api=`0` dry_run=`1` parser=`1`
