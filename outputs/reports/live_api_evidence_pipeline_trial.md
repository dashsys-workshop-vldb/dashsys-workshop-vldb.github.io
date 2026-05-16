# Live API Evidence Pipeline Trial

Infrastructure validation only; this report does not compute or claim official strict-score improvement.

- Status: `skipped_live_credentials_missing`
- Credentials present: `False`
- Live mode attempted: `False`
- Dry-run fallback verified: `True`
- Total prompts: `1`
- Live API executed count: `0`
- Dry-run fallback count: `1`
- Outcome counts: `{}`
- Parser success count: `1`
- Usable live API evidence count: `0`
- API state/caveat forwarded count: `0`
- Answer used usable API evidence count: `0`
- Answer used API state/caveat count: `0`
- Unsupported API claim count: `0`
- Live/dry-run mismatch count: `0`
- Recommendation: `provide_live_credentials_then_rerun`
- Residual risk: Live API execution, real payload parsing, EvidenceBus forwarding from live payloads, and auth/rate-limit handling remain unverified until Adobe credentials are available.

## Prompt Rows

- `dry_run_fallback_probe` live_api=`0` dry_run=`1` outcome=`None` usable_evidence=`0` api_state=`0`

## Metric Notes

- `usable_live_api_evidence_count` requires a live_success/live_empty outcome plus parsed payload evidence.
- `answer_used_api_state_count` is separate; it means the answer only used an API failure/unavailable caveat.
