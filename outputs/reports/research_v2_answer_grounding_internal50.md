# Research V2 Answer Grounding Internal50

Generated: 2026-05-28T16:02:55.924591+00:00

| Mode | Overall | Behavior | Final answer | Route | SQL calls | API calls | API underuse | No-tool FP | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `packaged_baseline_real` | 0.7168 | 0.8238 | 0.6525 | 0.8 | 40 | 33 | 0 | 0 | 0 |
| `robust_generalized_harness_candidate_v2_real` | 0.7784 | 0.8525 | 0.675 | 0.88 | 38 | 26 | 0 | 0 | 0 |

- Overall delta: `0.0616`
- Behavior delta: `0.0287`
- Helped/hurt/neutral: `8/0/42`
- SQL/API call deltas: `-2` / `-7`
- Per-category candidate: `{'ambiguous_low_confidence': 0.85, 'api_only_live_platform': 0.6562, 'conceptual_no_tool': 0.8396, 'hard_stress': 0.7463, 'mixed_conceptual_data': 0.774, 'sql_only_local_snapshot': 0.8135, 'sql_then_api_verification': 0.8708}`

No promotion recommendation.
