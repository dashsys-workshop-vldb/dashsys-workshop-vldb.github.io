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
- EvidenceBus API evidence count: `0`
- Answer used API evidence count: `9`
- Unsupported API claim count: `0`
- Live/dry-run mismatch count: `0`
- Recommendation: `inspect_live_payload_gaps_before_any_score_claim`
- Residual risk: Only safe GET calls are allowed; POST/mutation and unresolved path-param calls are blocked by the trial guard.

## Prompt Rows

- `example_000` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_001` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_002` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_003` live_api=`2` dry_run=`0` outcome=`api_error` parser=`0`
- `example_004` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_005` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_006` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_007` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
- `example_008` live_api=`0` dry_run=`0` outcome=`None` parser=`0`
- `example_009` live_api=`1` dry_run=`0` outcome=`api_error` parser=`0`
