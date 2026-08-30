# Live API Evidence Arbitration Trial

- Current live baseline score: `0.6247`
- Pre-live baseline score: `0.6553`
- Recommended variant: `sql_primary_when_complete`
- Promotion decision: `promote_arbitration_policy`

| Variant | Strict score | Delta vs live | Delta vs pre-live | Helped | Hurt |
|---|---:|---:|---:|---:|---:|
| `current_live_baseline` | `0.6247` | `0.0000` | `-0.0306` | `0` | `0` |
| `sql_primary_when_complete` | `0.6343` | `0.0096` | `-0.0210` | `3` | `0` |
| `live_api_primary_only_when_required` | `0.6343` | `0.0096` | `-0.0210` | `3` | `0` |
| `conflict_explicit` | `0.6247` | `0.0000` | `-0.0306` | `0` | `0` |
| `suppress_noisy_live_verification` | `0.6240` | `-0.0007` | `-0.0313` | `4` | `4` |
