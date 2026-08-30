
# Research Generalized V2 Internal 50

| Mode | Overall | Behavior | Final Answer | No-tool FP | No-tool FN | API Underuse | Unsupported | API Calls | SQL Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| packaged_baseline_real | 0.6743 | 0.7904 | 0.6325 | 0 | 10 | 0 | 0 | 33 | 35 | 1034.16 |
| robust_generalized_harness_candidate_v2_real | 0.7843 | 0.8529 | 0.6675 | 0 | 0 | 0 | 0 | 26 | 28 | 845.94 |

Helped/hurt/neutral: 11/0/39
SQL/API call delta: -7/-7
Per-category candidate: `{'api_only_live_platform': 0.6495, 'conceptual_no_tool': 0.8396, 'hard_stress': 0.8096, 'mixed_conceptual_data': 0.8, 'sql_only_local_snapshot': 0.8227}`
