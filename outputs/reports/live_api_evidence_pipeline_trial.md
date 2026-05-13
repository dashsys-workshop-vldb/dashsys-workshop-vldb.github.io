# Live API Evidence Pipeline Trial

Infrastructure validation only; this report does not compute or claim official strict-score improvement.

- Status: `complete`
- Credentials present: `True`
- Live mode attempted: `True`
- Dry-run fallback verified: `False`
- Total prompts: `10`
- Live API executed count: `10`
- Dry-run fallback count: `0`
- Outcome counts: `{'api_error': 10}`
- Parser success count: `0`
- Usable live API evidence count: `0`
- API state/caveat forwarded count: `10`
- Answer used usable API evidence count: `0`
- Answer used API state/caveat count: `9`
- Unsupported API claim count: `0`
- Live/dry-run mismatch count: `0`
- Recommendation: `inspect_live_payload_gaps_before_any_score_claim`
- Residual risk: Only safe GET calls are allowed; POST/mutation and unresolved path-param calls are blocked by the trial guard.

## Prompt Rows

- `example_000` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_001` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_002` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_003` live_api=`2` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`2`
- `example_004` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_005` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_006` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_007` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`
- `example_008` live_api=`0` dry_run=`0` outcome=`None` usable_evidence=`0` api_state=`0`
- `example_009` live_api=`1` dry_run=`0` outcome=`api_error` usable_evidence=`0` api_state=`1`

## Metric Notes

- `usable_live_api_evidence_count` requires a live_success/live_empty outcome plus parsed payload evidence.
- `answer_used_api_state_count` is separate; it means the answer only used an API failure/unavailable caveat.
