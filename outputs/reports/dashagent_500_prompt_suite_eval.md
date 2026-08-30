# DashAgent 500-Prompt Suite Eval

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

### semantic_routing_shadow
- overall_score: 0.8955
- route_accuracy: 0.8795
- observable_trace_score: 0.9117
- sql_accuracy: 0.958
- api_accuracy: 0.918
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 60
- api_calls_saved: 0
- api_calls_added: 0
- anti_hallucination_initial_fail: 43
- anti_hallucination_revision_success: 43
- post_sql_advisor_invoked: 0
- post_sql_advisor_verified: 0
- post_sql_advisor_blocked: 0

### staged_evidence_shadow
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

### post_sql_api_decision_shadow
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
- post_sql_advisor_invoked: 3
- post_sql_advisor_verified: 1
- post_sql_advisor_blocked: 2

### latest_applied_trial
- overall_score: 0.8961
- route_accuracy: 0.853
- observable_trace_score: 0.9003
- sql_accuracy: 0.841
- api_accuracy: 0.974
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 60
- api_calls_saved: 57
- api_calls_added: 53
- anti_hallucination_initial_fail: 43
- anti_hallucination_revision_success: 43
- post_sql_advisor_invoked: 3
- post_sql_advisor_verified: 1
- post_sql_advisor_blocked: 2
