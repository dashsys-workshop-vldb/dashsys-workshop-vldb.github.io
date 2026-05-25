# Strict Score Drift Analysis

This diagnostic compares the archived pre-live strict baseline, the post-live arbitration reference, and the current fresh strict result.

- Strategy: `SQL_FIRST_API_VERIFY`
- Non-regression reference: `0.6553`
- Pre-live strict score: `0.6553`
- Post-live arbitration reference: `0.6247`
- Current fresh strict score: `0.6567`
- Primary root cause: `no_clear_drift`
- Reason: See row-level deltas.

## Row Summary

- Rows helped: `16`
- Rows hurt: `19`
- Rows unchanged: `0`

## Top Negative Deltas

- `example_033` delta `-0.1244` category `evidencebus_field_drift`
- `example_034` delta `-0.1104` category `evidencebus_field_drift`
- `example_015` delta `-0.1098` category `evidencebus_field_drift`
- `example_016` delta `-0.1088` category `evidencebus_field_drift`
- `example_009` delta `-0.1043` category `api_endpoint_selection_drift`
- `example_002` delta `-0.0756` category `evidencebus_field_drift`
- `example_005` delta `-0.0755` category `evidencebus_field_drift`
- `example_014` delta `-0.0453` category `evidencebus_field_drift`
- `example_003` delta `-0.0408` category `evidencebus_field_drift`
- `example_022` delta `-0.036` category `evidencebus_field_drift`

No runtime fix is applied by this script.