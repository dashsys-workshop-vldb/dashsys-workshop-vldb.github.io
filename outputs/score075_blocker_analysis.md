# Score 0.75 Blocker Analysis

- Best achieved score: 0.6556
- Score gap remaining: 0.0944
- Recommendation: `submit_current_official_token_reduction_version`
- Current version should remain submit-ready: True

## Why 0.75 Was Not Reached

- strict_final_score_0_75_not_reached

## Tried Strategies

- `score_component_error_report`: {'api_correct_answer_weak_rows': 16, 'current_avg_final_score': 0.6491, 'likely_bottleneck_counts': {'api_bottleneck': 2, 'api_correct_answer_weak': 16, 'candidate_or_efficiency_limit': 7, 'dry_run_evidence_limitation': 10}, 'packaged_execution_changed': False, 'target_score': 0.75, 'top_api_correct_answer_weak_rows': ['example_017', 'example_030', 'example_031', 'example_029', 'example_019', 'example_028', 'example_025', 'example_024', 'example_020', 'example_021'], 'top_target_rows': ['example_017', 'example_030', 'example_031', 'example_029', 'example_019', 'example_028', 'example_025', 'example_024', 'example_020', 'example_021'], 'total_rows': 35, 'total_score_gap_to_0_75': 3.8106}
- `evidence_answer_candidate_eval`: {'answer_only_sql_api_unchanged_rows': 10, 'best_projected_strict_final_score': 0.6494, 'local_evidence_available_rows': 10, 'local_evidence_used_rows': 0, 'packaged_execution_changed': False, 'recommendation': 'safe_for_autonomous_packaged_trial', 'requested_fact_covered_rows': 10, 'safe_rows': 1, 'selected_query_ids': ['example_025'], 'target_0_75_reached': False, 'total_rows': 10, 'unsafe_rows': 9}
- `unsafe_answer_candidate_analysis`: {'category_counts': {'answer_drift': 8, 'dry_run_label_loss': 2, 'runtime_or_tool_gate': 24, 'token_gate_failed': 9}, 'packaged_execution_changed': False, 'positive_supportable_rows': 10, 'top_supportable_rows': ['example_031', 'example_030', 'example_021', 'example_025', 'example_024', 'example_029', 'example_028', 'example_031', 'example_030', 'example_019'], 'total_rows': 24}
- `supportable_answer_rewrite_eval`: {'best_projected_strict_final_score': 0.655, 'hash_preserved_rows': 10, 'packaged_execution_changed': False, 'recommendation': 'safe_for_autonomous_packaged_trial', 'safe_rows': 5, 'selected_query_ids': ['example_031', 'example_030', 'example_025', 'example_029', 'example_020'], 'target_0_75_reached': False, 'total_rows': 10, 'unsafe_rows': 5}
- `local_index_fact_coverage_report`: {'data_json_used_for_runtime': False, 'evidence_object_count': 1033, 'local_evidence_available_rows': 34, 'local_evidence_used_in_final_answer_rows': 24, 'local_index_returns_final_answers': False, 'packaged_execution_changed': False, 'requested_fact_covered_rows': 34, 'score_delta_from_local_evidence_total': 0.0, 'total_rows': 35}
- `execution_candidate_search`: {'best_projected_strict_final_score': 0.6556, 'best_total_score_delta': 0.2261, 'candidate_rejection_reason_counts': {'api_unsafe_drift': 17, 'api_validation_failed': 2, 'dry_run_labels_not_preserved': 9, 'evidence_label_loss': 9, 'final_answer_unsafe_drift': 7, 'invalid_api_detected': 2, 'no_accuracy_relevant_candidate_change': 28, 'no_score_or_correctness_improvement': 23, 'runtime_gate_failed': 1, 'sql_unsafe_drift': 2, 'token_gate_failed': 3, 'tool_increase_without_substantial_score_gain': 1, 'unresolved_api_placeholders': 2}, 'fallback_safe_improvement': True, 'packaged_execution_changed': False, 'recommendation': 'safe_for_targeted_packaged_trial', 'safe_rows': 5, 'selected_query_ids': ['example_030', 'example_031', 'example_029', 'example_019', 'example_025'], 'target_0_70_reached': False, 'total_target_rows': 10, 'unsafe_rows': 5}
- `llm_candidate_search`: {'failure_category_counts': {}, 'recommendation': 'keep_shadow_only', 'safe_rows': 0, 'status': 'skipped_no_llm_key', 'unsafe_rows': 0}
- `llm_answer_rewrite_search`: {'candidate_rows': 0, 'failure_category_counts': {}, 'provider': None, 'recommendation': 'keep_shadow_only', 'safe_rows': 0, 'status': 'skipped_no_llm_key', 'total_rows': 0, 'unsafe_rows': 0}
- `autonomous_packaged_trial`: {'baseline_strict_final_score': 0.6491, 'correctness': 0.6807, 'correctness_delta': 0.0064, 'estimated_tokens': 827.7714, 'gates': {'all_rows_safe': True, 'correctness_not_regressed': True, 'final_submission_ready': True, 'hidden_style_48_of_48': True, 'no_secret_scan_ok': True, 'protected_hashes_unchanged': True, 'runtime_within_10pct': True, 'strict_score_improved': True, 'strict_score_target_0_75': False, 'tokens_within_2pct': True, 'tool_calls_not_increased': True}, 'recommendation': 'continue_iteration_target_not_reached', 'runtime': 0.0096, 'runtime_delta': -0.0013, 'safe_rows': 6, 'score_delta': 0.0065, 'strict_final_score': 0.6556, 'target_0_70_reached': False, 'target_0_75_reached': False, 'target_0_80_reached': False, 'token_delta': -3.6857, 'tool_calls': 1.4571, 'tool_delta': 0.0, 'total_rows': 6, 'unsafe_rows': 0}

## Remaining High-Potential Rows

- `example_017`: no_supportable_candidate_passed_all_gates
- `example_030`: runtime_or_tool_gate; token_gate_failed
- `example_031`: runtime_or_tool_gate; token_gate_failed
- `example_029`: runtime_or_tool_gate; token_gate_failed
- `example_019`: no_supportable_candidate_passed_all_gates
- `example_028`: no_supportable_candidate_passed_all_gates
- `example_025`: runtime_or_tool_gate
- `example_024`: no_supportable_candidate_passed_all_gates
- `example_020`: runtime_or_tool_gate; token_gate_failed
- `example_021`: no_supportable_candidate_passed_all_gates
