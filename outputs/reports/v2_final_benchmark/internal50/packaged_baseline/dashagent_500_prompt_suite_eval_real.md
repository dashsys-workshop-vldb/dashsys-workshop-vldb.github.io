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
- prompt_count: 50
- latest_code_paths_explicitly_evaluated: false
- old_generated_diagnostic_path_used: false

## Modes
### packaged_baseline_real
- behavior_score: 0.8238
- trace_observability_score: 0.245
- combined_diagnostic_score: 0.7168
- overall_score_alias: 0.7168
- route_accuracy: 0.8
- observable_trace_score: 0.6117
- sql_accuracy: 0.85
- api_accuracy: 0.76
- unsupported_claims: 0
- no_tool_false_positive: 0
- no_tool_false_negative: 3
- api_calls_saved: 0
- api_calls_added: 0
- anti_hallucination_initial_fail: 0
- anti_hallucination_revision_success: 0
- post_sql_advisor_note: checkpoints are observability; actual LLM calls are counted separately
- post_sql_advisor_checkpoint_present_count: 0
- post_sql_llm_advisor_actual_call_count: 0
- post_sql_deterministic_fallback_count: 0
- post_sql_llm_advice_blocked_count: 0
- post_sql_verifier_verified_count: 0
- post_sql_verifier_blocked_count: 0
- post_sql_advisor_source_counts: {'DETERMINISTIC_BYPASS': 0, 'DETERMINISTIC_FALLBACK': 0, 'DETERMINISTIC_HIGH_CONF': 0, 'DISABLED': 0, 'INVALID_JSON': 0, 'LLM_ADVISOR': 0, 'LLM_ADVISOR_BLOCKED': 0, 'LLM_ADVISOR_VERIFIED': 0, 'LLM_BACKEND_UNAVAILABLE': 0}
