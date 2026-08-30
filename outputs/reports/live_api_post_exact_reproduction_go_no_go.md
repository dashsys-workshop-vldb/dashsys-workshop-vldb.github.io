# Live API Post Exact Reproduction Go/No-Go

- Recommendation: `promote_arbitration_policy_only`
- PATH B direct exact: `{'outcome': 'live_success', 'status_code': 200}`
- PATH C repo equivalence: `{'outcome': 'live_success', 'status_code': 200}`
- Normal runtime UPS audiences: `{'outcome': 'live_success', 'status_code': 200}`

## Score Regression Resolution
- Pre-live baseline strict score: `0.6553`
- Initial live strict score: `0.6247`
- Current live strict score: `0.6555`
- Live API remains enabled: `True`

## Endpoint Coverage
- Safe GET attempted: `15`
- Live success/live empty: `10` / `5`
- Endpoint path issues/API errors: `0` / `0`

## Post-Live Robustness
- Arbitration policy safe: `True`; critical violations `0`
- Generated diagnostic prompts: `250`/`250` runtime pass, validation failures `0`, unsupported claims `0`
- Generated diagnostic API outcomes: live success `65`, live empty `8`, API error `139`, dry run `0`
- Template dependency score: `0.1634`; template miss rate `0.6488`; paraphrase consistency `0.9907`
- Schema-aware SQL: `keep_trial_only`
- Controller rewrite trial: `backend_answer_only_shadow_candidate`; multi-LLM calls executed `0`
- Integrated gate: `promote_arbitration_policy_only`

## Validation
- Hidden-style: `48/48`
- Guarded live E2E status: `pass`
