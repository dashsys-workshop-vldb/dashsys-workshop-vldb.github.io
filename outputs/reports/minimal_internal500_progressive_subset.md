# Minimal Internal 500 Progressive Subset

- Scope: balanced 50-row subset only
- Real AgentExecutor execution: `true`
- Synthetic trace: `false`
- Organizer-equivalent: `false`
- Promotion judgment: `not_run`

## Mode Summary

| Mode | Behavior | Final Answer | Trace Obs | Combined | SQL Acc | API Acc | SQL Calls | API Calls | Unsupported | No-tool FP | API Underuse | Runtime ms | Avg Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `packaged_baseline_real` | 0.7708 | 0.605 | 0.25 | 0.6486 | 0.76 | 0.8 | 30 | 39 | 0 | 0 | 0 | 36.1751 | 973.82 |
| `robust_generalized_harness_candidate_real` | 0.805 | 0.63 | 0.365 | 0.718 | 0.72 | 0.76 | 24 | 27 | 0 | 4 | 0 | 858.7317 | 720.88 |

## Deltas
- Behavior delta: `0.0342`
- Overall/combined delta: `0.0694`
- SQL call delta: `-6`
- API call delta: `-12`
- Runtime delta ms: `822.5566`
- Token delta: `-252.94`
- Helped/hurt/neutral: `{'helped': 10, 'hurt': 4, 'neutral': 36}`

## Results By Category

| Category | Baseline | Candidate |
|---|---:|---:|
| `api_only_live_platform` | 0.6287 | 0.6433 |
| `conceptual_no_tool` | 0.3827 | 0.8396 |
| `hard_stress` | 0.7148 | 0.5531 |
| `mixed_conceptual_data` | 0.7789 | 0.7956 |
| `sql_only_local_snapshot` | 0.7377 | 0.7585 |

## Hurt Rows
- `da500_0492` `wrong_no_tool_skip` delta `-0.375` (hard_stress/DATASET): In one answer, define dataset and provide current evidence where available. Keep the answer evidence-bound for the readiness reviewal.
- `da500_0447` `wrong_no_tool_skip` delta `-0.3333` (hard_stress/MERGE_POLICY): In one answer, define merge policy and provide current evidence where available. Keep the answer evidence-bound for the operations digest.
- `da500_0497` `wrong_no_tool_skip` delta `-0.3333` (hard_stress/BATCH): In one answer, define batch and provide current evidence where available. Keep the answer evidence-bound for the stewardship reviewal.
- `da500_0486` `wrong_no_tool_skip` delta `-0.2709` (hard_stress/DESTINATION): Without using the word list, return available destination records from evidence. Keep the answer evidence-bound for the quality reviewal.

## Interpretation
Minimal balanced subset only, not organizer-equivalent and not a promotion gate. Candidate improved behavior score on this subset but still produced 4 wrong no-tool skips in hard-stress rows.
