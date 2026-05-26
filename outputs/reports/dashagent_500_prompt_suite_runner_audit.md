# DashAgent 500-Prompt Suite Runner Audit

- old_synthetic_eval_issue_found: True
- old_synthetic_eval_issue_fixed: True
- eval_engine: real_agent
- simulated_trace_only: False
- synthetic_sql_result_used: False
- category_tags_influenced_runtime: False
- agent_executor_used: True
- gold_hidden_from_runtime: True
- runtime_input_fields: ['prompt_id', 'prompt']
- oracle_sql_hidden_from_runtime: True
- expected_trace_hidden_from_runtime: True
- latest_code_paths_truly_executed: True
- latest_code_paths_shadow_logged_only: True
- latest_applied_real_trial_available: False
- notes:
  - Simulated trace mode is retained only as a diagnostic compatibility engine.
  - Real-agent mode uses AgentExecutor.run and writes actual per-prompt trajectory.json files.
  - Gold, oracle SQL, expected traces, category, domain, and tags are grading inputs only in real-agent mode.
