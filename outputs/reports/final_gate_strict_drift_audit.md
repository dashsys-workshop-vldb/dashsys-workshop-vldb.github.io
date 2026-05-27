# Final Gate Strict Drift Audit

## Conclusion
The final gate failure was caused by strict-score baseline drift from runtime/efficiency variance, not by a measured SQL/API/answer behavior regression from `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`. The packaged default remains `SQL_FIRST_API_VERIFY`.

## Strict Snapshots
| Snapshot | Final | Correctness | SQL | API | Answer | Runtime | Tokens | Tool calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| previous_promotion_review_sql_first | 0.6579 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 0.642 | 799.4571 | 1.4571 |
| previous_promotion_review_combined_safe | 0.6584 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 0.5034 | 799.6 | 1.4571 |
| final_gate_candidate_before_rollback | 0.6539 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 1.8819 | 799.2571 | 1.4571 |
| final_gate_sql_first_before_rollback_run | 0.6533 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 2.0581 | 799.2 | 1.4571 |
| current_sql_first_rerun_1 | 0.6522 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 2.5058 | 790.9143 | 1.4571 |
| current_sql_first_rerun_2 | 0.65 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 3.2873 | 790.8286 | 1.4571 |
| current_sql_first_fair_comparison | 0.6492 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 3.6795 | 790.8571 | 1.4571 |
| current_candidate_fair_comparison | 0.6513 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 2.7249 | 790.9143 | 1.4571 |
| token_reduction_disabled_sql_first | 0.6437 | 0.6814 | 0.9333 | 0.9791 | 0.3135 | 3.1135 | 1187.1714 | 1.4571 |

## Current SQL_FIRST Run-To-Run Variance
| Metric | Values | Range |
|---|---:|---:|
| avg_final_score | [0.6522, 0.65, 0.6492] | 0.003 |
| avg_correctness_score | [0.6851, 0.6851, 0.6851] | 0.0 |
| avg_sql_score | [0.9333, 0.9333, 0.9333] | 0.0 |
| avg_api_score | [0.9791, 0.9791, 0.9791] | 0.0 |
| avg_answer_score | [0.3209, 0.3209, 0.3209] | 0.0 |
| avg_runtime | [2.5058, 3.2873, 3.6795] | 1.1737 |
| avg_execution_time | [2.4709, 3.2527, 3.6443] | 1.1734 |
| avg_estimated_tokens | [790.9143, 790.8286, 790.8571] | 0.0857 |
| avg_tool_call_count | [1.4571, 1.4571, 1.4571] | 0.0 |

## Current Fair Comparison
| Metric | SQL_FIRST | Candidate | Delta |
|---|---:|---:|---:|
| avg_final_score | 0.6492 | 0.6513 | 0.0021 |
| avg_correctness_score | 0.6851 | 0.6851 | 0.0 |
| avg_sql_score | 0.9333 | 0.9333 | 0.0 |
| avg_api_score | 0.9791 | 0.9791 | 0.0 |
| avg_answer_score | 0.3209 | 0.3209 | 0.0 |
| avg_runtime | 3.6795 | 2.7249 | -0.9546 |
| avg_execution_time | 3.6443 | 2.6824 | -0.9619 |
| avg_estimated_tokens | 790.8571 | 790.9143 | 0.0572 |
| avg_tool_call_count | 1.4571 | 1.4571 | 0.0 |

## Rows Responsible For Drift
Rows with the largest prior-to-current SQL_FIRST final-score drops are runtime/efficiency classified unless their SQL/API/answer/tool behavior changed.

| Query | Prior SQL_FIRST | Current SQL_FIRST | Delta | Current runtime | Classification |
|---|---:|---:|---:|---:|---|
| example_026 | 0.6625 | 0.5843 | -0.0782 | 24.5145 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_022 | 0.5325 | 0.4561 | -0.0764 | 37.2747 | runtime_efficiency_changed |
| example_027 | 0.6079 | 0.5804 | -0.0275 | 8.7109 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_013 | 0.7387 | 0.718 | -0.0207 | 7.2431 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_015 | 0.5549 | 0.5355 | -0.0194 | 6.9618 | runtime_efficiency_changed |
| example_034 | 0.5519 | 0.5395 | -0.0124 | 4.3056 | tool_or_answer_score_changed |
| example_000 | 0.6902 | 0.6785 | -0.0117 | 6.0597 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_025 | 0.8158 | 0.8042 | -0.0116 | 3.9098 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_009 | 0.6542 | 0.6481 | -0.0061 | 2.223 | runtime_efficiency_changed, run_to_run_efficiency_variance |
| example_017 | 0.6229 | 0.6169 | -0.006 | 2.4384 | runtime_efficiency_changed, run_to_run_efficiency_variance |

## APIValidator Hardening
Current SQL_FIRST placeholder-blocked rows: `1`.
- `example_003`: blocked unresolved API parameter placeholder before network execution.

The blocked call was invalid and the hardening should be kept. No current normal strict run showed SQL/API/answer/correctness regression from the hardening.

## Token Reduction
Disabling the full official token-reduction feature changed token budget and answer metrics, so it is not a clean isolation of warning preservation. Warning preservation itself only keeps unresolved-parameter warnings in compacted trajectory/readiness metadata and should remain enabled.

## Recommendation
`keep_trial_only_due_to_baseline_drift`: candidate remains behavior-identical or faster under current code, but promotion should wait until the strict baseline is stable enough for a final default-flip gate.

## Final Validation
- Normal strict SQL_FIRST final: `0.6515`; correctness `0.6851`; SQL `0.9333`; API `0.9791`; answer `0.3209`.
- Hidden-style: `48/48` passed.
- check_submission_ready: `ok=true`, query outputs `73`, default `SQL_FIRST_API_VERIFY`.
- pytest: `692 passed, 1 skipped`.
- git diff --check: passed.
- Secret scan: `ok=true`, real hits `0`, fixture false positives `3`.
