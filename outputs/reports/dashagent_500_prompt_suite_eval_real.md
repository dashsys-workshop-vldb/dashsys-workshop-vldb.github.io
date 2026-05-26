# DashAgent 500-Prompt Suite Eval

- eval_engine: real_agent
- real_agent_execution: true
- simulated_trace_only: false
- synthetic_sql_results_used: false
- runtime_used_category_tags_for_decision: false
- agent_executor_used: true
- grading_type: heuristic_internal_gold
- organizer_equivalent: false
- answer_grading_method: required_fact_substring_and_forbidden_claim_checks
- process_grading_method: observable_trace_checkpoint_and_tool_usage_matching
- prompt_count: 500
- latest_code_paths_explicitly_evaluated: true
- old_generated_diagnostic_path_used: false

## Modes
### packaged_baseline_real
- behavior_score: 0.8045
- trace_observability_score: 0.2495
- combined_diagnostic_score: 0.6995
- overall_score_alias: 0.6995
- route_accuracy: 0.752
- observable_trace_score: 0.5979
- sql_accuracy: 0.84
- api_accuracy: 0.772
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 69
- api_calls_saved: 0
- api_calls_added: 0
- anti_hallucination_initial_fail: 0
- anti_hallucination_revision_success: 0
- post_sql_advisor_invoked: 0
- post_sql_advisor_verified: 0
- post_sql_advisor_blocked: 0

### latest_shadow_real
- behavior_score: 0.8045
- trace_observability_score: 0.4993
- combined_diagnostic_score: 0.7203
- overall_score_alias: 0.7203
- route_accuracy: 0.752
- observable_trace_score: 0.6812
- sql_accuracy: 0.84
- api_accuracy: 0.772
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 69
- api_calls_saved: 0
- api_calls_added: 0
- anti_hallucination_initial_fail: 0
- anti_hallucination_revision_success: 0
- post_sql_advisor_invoked: 327
- post_sql_advisor_verified: 0
- post_sql_advisor_blocked: 101
