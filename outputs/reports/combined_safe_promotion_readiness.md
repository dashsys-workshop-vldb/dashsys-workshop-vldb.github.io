# Combined Safe Promotion Readiness

- grading_type: heuristic_internal_gold
- organizer_equivalent: False
- baseline_behavior_score: 0.8045
- combined_safe_behavior_score: 0.8185
- behavior_delta: 0.014
- final_answer_correctness_delta: 0.0173
- api_calls_saved: 70
- token_delta: -1.82
- runtime_delta_ms: 14.6108
- unsupported_claim_count: 0
- no_tool_false_positives: 0
- api_required_underuse: 0
- rows_helped/hurt/neutral: 69/1/430
- remaining_hurt_rows_acceptable: True
- llm_advisor_rejected: True
- packaged_runtime_changed: False
- final_submission_format_changed: False
- recommendation: ready_for_targeted_promotion_review

## Hurt Rows
### da500_0446
- pre_fix_classification: true_policy_bug
- post_fix_status: resolved
- post_fix_behavior_score: 0.8542
- post_fix_api_calls: 1

### da500_0441
- pre_fix_classification: acceptable_efficiency_tradeoff
- post_fix_status: remaining_hurt_row
- post_fix_behavior_score: 0.7917
- post_fix_api_calls: 0

## Remaining Hurt Rationale
The sole remaining hurt row has API optional in gold and unchanged final answer correctness; the behavior-score loss comes from optional API family/tool-use heuristic pressure, while the trial avoids an unnecessary API call.
