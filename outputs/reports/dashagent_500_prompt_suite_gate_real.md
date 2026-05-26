# DashAgent 500-Prompt Suite Gate

- passed: False
- diagnostic_gate_only: True
- packaged_runtime_changed: False
- final_submission_format_changed: False
- eval_engine: real_agent
- simulated_trace_only: False
- real_agent_execution: True
- baseline_score: 0.6995
- latest_trial_score: None
- route_trace_accuracy: 0.0
- unsupported_claims_zero: True
- no_tool_false_positive: 0
- api_calls_saved: 0
- api_calls_added: 0
- runtime_cost_acceptable: False
- latest_code_paths_explicitly_evaluated: True
- recommendation: improve_post_sql_policy_before_promotion
- blockers: ['Semantic route decisions are integrated as shadow checkpoints only.', 'Staged evidence policy is integrated as shadow checkpoints only.', 'Post-SQL API decision policy records keep/drop/add advice but does not alter actual API execution.', 'No non-shadow promotion gate has approved applying these decisions to packaged execution.']
