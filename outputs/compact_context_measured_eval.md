# Compact Context Measured Evaluation

Measured efficiency improvement is experimental only, not packaged-submission improvement.

- Packaged execution changed: False
- Official measured efficiency improvement claimed: False
- Experiment measured efficiency improvement claimed: False
- No behavior-changing flags were enabled in this pass.
- Total rows: 35
- Eligible rows: 28
- Skipped rows: 7
- Safe-to-enable rows: 0
- Unsafe rows: 28
- Avg score delta: -0.0
- Avg token delta: 4.3214
- Avg total token delta: 4.3214
- Avg context-only token delta: 206.75
- Avg checkpoint-overhead token delta: 232.5
- Avg runtime delta: 0.0016
- Avg tool delta: 0.0
- Recommendation: `unsafe_do_not_enable`

## Token Accounting Analysis

- Avg total estimated-token delta: 4.3214
- Avg context-only prompt-token delta: 206.75
- Avg compact checkpoint-overhead token delta: 232.5
- Classification counts: `{"context_and_total_improved": 0, "context_metric_unavailable_or_unreliable": 0, "context_only_improved_total_not_improved": 8, "total_tokens_not_improved": 20}`
- Official current context already compact-like rows: 28
- Fallback context tokens are diagnostic estimates: True
- Estimated token source: trajectory estimated_tokens = estimate_tokens({query, non-diagnostic steps, answer})
- Checkpoint overhead included in total tokens: False
- Metric mismatch explanation: some rows had context-only savings, but average context proxy and total estimated tokens did not improve

## Measurement Caveat

Schema-vote fallback_context_tokens is a broader-context diagnostic estimate, not necessarily the official current prompt size. The official current path can already be compact-like, so replacing it with schema-vote compact metadata may not save prompt tokens. The official trajectory estimated_tokens metric is computed from query, compact step records, and final answer; it excludes checkpoints and the full filled prompt/context payload. Therefore large replay-estimated context savings can coexist with flat or positive measured total estimated_tokens.

| Query ID | Eligible | Skip reason | Score delta | Total token delta | Context token delta | Runtime delta | Tool delta | Token classification | Safe? |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `example_000` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_001` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_002` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_003` | True |  | -0.0001 | 4 | 492 | 0.005 | 0 | total_tokens_not_improved | False |
| `example_004` | True |  | -0.0001 | 4 | 432 | 0.0023 | 0 | total_tokens_not_improved | False |
| `example_005` | True |  | -0.0001 | 5 | 865 | 0.0019 | 0 | total_tokens_not_improved | False |
| `example_006` | True |  | -0.0001 | 5 | 421 | 0.0042 | 0 | total_tokens_not_improved | False |
| `example_007` | True |  | 0.0 | 4 | 30 | 0.0023 | 0 | total_tokens_not_improved | False |
| `example_008` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_009` | True |  | 0.0 | 5 | 214 | 0.0031 | 0 | total_tokens_not_improved | False |
| `example_010` | True |  | 0.0 | 4 | 479 | 0.0033 | 0 | total_tokens_not_improved | False |
| `example_011` | True |  | -0.0001 | 5 | 917 | 0.0032 | 0 | total_tokens_not_improved | False |
| `example_012` | True |  | -0.0001 | 5 | 461 | 0.0043 | 0 | total_tokens_not_improved | False |
| `example_013` | True |  | 0.0 | 5 | 716 | 0.004 | 0 | total_tokens_not_improved | False |
| `example_014` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_015` | True |  | 0.0 | 3 | -131 | 0.0009 | 0 | context_only_improved_total_not_improved | False |
| `example_016` | True |  | -0.0001 | 3 | -133 | 0.0006 | 0 | context_only_improved_total_not_improved | False |
| `example_017` | True |  | 0.0 | 5 | 327 | 0.0009 | 0 | total_tokens_not_improved | False |
| `example_018` | True |  | 0.0 | 4 | -336 | 0.0004 | 0 | context_only_improved_total_not_improved | False |
| `example_019` | True |  | 0.0 | 4 | -137 | 0.0008 | 0 | context_only_improved_total_not_improved | False |
| `example_020` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_021` | True |  | 0.0 | 4 | -58 | 0.0006 | 0 | context_only_improved_total_not_improved | False |
| `example_022` | True |  | -0.0001 | 5 | 210 | 0.001 | 0 | total_tokens_not_improved | False |
| `example_023` | True |  | -0.0001 | 5 | 207 | 0.0006 | 0 | total_tokens_not_improved | False |
| `example_024` | True |  | 0.0 | 5 | 209 | 0.0007 | 0 | total_tokens_not_improved | False |
| `example_025` | True |  | -0.0001 | 5 | 207 | 0.0011 | 0 | total_tokens_not_improved | False |
| `example_026` | True |  | 0.0 | 5 | 209 | 0.0007 | 0 | total_tokens_not_improved | False |
| `example_027` | True |  | 0.0 | 5 | 199 | 0.0007 | 0 | total_tokens_not_improved | False |
| `example_028` | True |  | 0.0 | 4 | 290 | 0.0005 | 0 | total_tokens_not_improved | False |
| `example_029` | True |  | 0.0 | 3 | -238 | 0.0009 | 0 | context_only_improved_total_not_improved | False |
| `example_030` | True |  | 0.0 | 4 | -407 | -0.0006 | 0 | context_only_improved_total_not_improved | False |
| `example_031` | True |  | 0.0 | 4 | 286 | 0.001 | 0 | total_tokens_not_improved | False |
| `example_032` | True |  | 0.0 | 4 | 314 | 0.0012 | 0 | total_tokens_not_improved | False |
| `example_033` | False | risk_level is not high; schema_vote_agreement is not true; compact_context_safe is not true; compact and fallback top tables do not agree | None | None | None | None | None | context_metric_unavailable_or_unreliable | False |
| `example_034` | True |  | 0.0 | 3 | -256 | 0.0002 | 0 | context_only_improved_total_not_improved | False |
