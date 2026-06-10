# Core Tool Correctness Trials

- Baseline strategy: `SQL_FIRST_API_VERIFY`
- Writes official eval artifacts: `False`
- Writes final submission: `False`

- `SQL_A` aggregate_alias_answer_slot_fix: strict delta `0.0`, recommendation `keep_trial_only`
- `SQL_B` status_date_field_preservation: strict delta `0.0`, recommendation `needs_strict_evidence_before_promotion`
- `SQL_C` schema_synonym_column_ranking: strict delta `0.0`, recommendation `keep_trial_only`
- `SQL_D` join_path_family_rerank: strict delta `0.0`, recommendation `keep_trial_only`
- `SQL_E` validation_safe_repair: strict delta `0.0`, recommendation `keep_trial_only`
- `API_A` required_id_gate_and_unresolved_placeholder_state: strict delta `0.0`, recommendation `already_covered_keep_regression_test`
- `API_B` api_outcome_state_consistency: strict delta `0.0`, recommendation `needs_strict_evidence_before_promotion`
- `API_C` sql_to_api_id_forwarding_check: strict delta `0.0`, recommendation `wait_for_adobe_access`
- `COMBINED_SAFE` combined_safe_correctness_tool_policy: strict delta `0.0`, recommendation `keep_trial_only`
