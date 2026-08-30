# Live API Score Regression Analysis

- Baseline strict score: `0.6553`
- Live strict score: `0.6247`
- Delta: `-0.0306`
- Rows helped/hurt/unchanged: `11` / `23` / `1`

## Dominant Categories
- `live_api_helped`: `11`
- `unnecessary_api_call_added_noise`: `6`
- `no_clear_regression`: `6`
- `endpoint_payload_shape_mismatch`: `5`
- `answer_wording_regression`: `4`
- `sql_api_conflict_unresolved`: `3`

## Biggest Negative Deltas
| query_id | delta | category |
|---|---:|---|
| `example_011` | `-0.1793` | `endpoint_payload_shape_mismatch` |
| `example_033` | `-0.1613` | `endpoint_payload_shape_mismatch` |
| `example_015` | `-0.1598` | `answer_wording_regression` |
| `example_004` | `-0.1533` | `sql_api_conflict_unresolved` |
| `example_034` | `-0.1466` | `endpoint_payload_shape_mismatch` |
| `example_016` | `-0.1255` | `answer_wording_regression` |
| `example_013` | `-0.1211` | `endpoint_payload_shape_mismatch` |
| `example_009` | `-0.1161` | `unnecessary_api_call_added_noise` |
