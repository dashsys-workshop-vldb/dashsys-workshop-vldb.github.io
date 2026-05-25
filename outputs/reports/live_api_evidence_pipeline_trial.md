# Live API Evidence Pipeline Trial

Infrastructure validation only; this report does not compute or claim official strict-score improvement.

- Status: `complete`
- Credentials present: `True`
- Live mode attempted: `True`
- Dry-run fallback verified: `False`
- Total prompts: `10`
- Live API calls attempted: `10`
- Live success count: `4`
- Live empty count: `5`
- Live API executed count: `10`
- Dry-run fallback count: `0`
- Outcome counts: `{'live_empty': 5, 'api_error': 1, 'live_success': 4}`
- Parser success count: `10`
- Usable live API evidence count: `4`
- API state/caveat forwarded count: `1`
- Answer used usable API evidence count: `2`
- Answer used API state/caveat count: `1`
- Unsupported API claim count: `0`
- Parser/EvidenceBus failure count: `0`
- Live/dry-run mismatch count: `0`
- Recommendation: `inspect_live_payload_gaps_before_any_score_claim`
- Residual risk: Only safe GET calls are allowed; POST/mutation and unresolved path-param calls are blocked by the trial guard.

## Query Records

| query_id | selected_endpoint | status | outcome | parser_status | usable_payload_entered_evidencebus | answer_used_actual_api_payload_evidence | answer_only_used_api_state_or_caveat | unsupported_claim |
|---|---|---|---|---|---|---|---|---|
| `example_000` | `journey_by_name` | `api_calls_executed` | `live_empty` | `pass` | `False` | `False` | `False` | `False` |
| `example_001` | `journey_inactive` | `api_calls_executed` | `live_empty` | `pass` | `False` | `False` | `False` | `False` |
| `example_002` | `journey_list` | `api_calls_executed` | `live_empty` | `pass` | `False` | `False` | `False` | `False` |
| `example_003` | `audience_by_destination_id` | `api_calls_executed` | `api_error` | `pass` | `True` | `False` | `True` | `False` |
| `example_004` | `failed_dataflow_flows` | `api_calls_executed` | `live_success` | `pass` | `True` | `True` | `False` | `False` |
| `example_005` | `recent_destination_flows` | `api_calls_executed` | `live_success` | `pass` | `True` | `True` | `False` | `False` |
| `example_006` | `datasets_by_schema` | `api_calls_executed` | `live_empty` | `pass` | `False` | `False` | `False` | `False` |
| `example_007` | `datasets_by_schema` | `api_calls_executed` | `live_success` | `pass` | `True` | `False` | `False` | `False` |
| `example_008` | `None` | `no_api_call` | `None` | `not_available` | `False` | `False` | `False` | `False` |
| `example_009` | `schema_by_name` | `api_calls_executed` | `live_empty` | `pass` | `False` | `False` | `False` | `False` |

## Metric Notes

- `usable_live_api_evidence_count` requires a live_success/live_empty outcome plus parsed payload evidence.
- `answer_used_api_state_count` is separate; it means the answer only used an API failure/unavailable caveat.
