# DashAgent 500-Prompt Suite Eval

- eval_engine: simulated_trace
- real_agent_execution: false
- simulated_trace_only: true
- synthetic_sql_results_used: true
- runtime_used_category_tags_for_decision: true
- agent_executor_used: false
- prompt_count: 500
- latest_code_paths_explicitly_evaluated: true
- old_generated_diagnostic_path_used: false

## Modes
### packaged_baseline
- overall_score: 0.89
- route_accuracy: 0.8595
- observable_trace_score: 0.9077
- sql_accuracy: 0.958
- api_accuracy: 0.918
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 60
- api_calls_saved: 0
- api_calls_added: 0
- anti_hallucination_initial_fail: 0
- anti_hallucination_revision_success: 0
- post_sql_advisor_invoked: 0
- post_sql_advisor_verified: 0
- post_sql_advisor_blocked: 0

### latest_applied_trial
- overall_score: 0.8925
- route_accuracy: 0.85
- observable_trace_score: 0.8954
- sql_accuracy: 0.834
- api_accuracy: 0.959
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 60
- api_calls_saved: 10
- api_calls_added: 83
- anti_hallucination_initial_fail: 43
- anti_hallucination_revision_success: 43
- post_sql_advisor_invoked: 3
- post_sql_advisor_verified: 1
- post_sql_advisor_blocked: 2
