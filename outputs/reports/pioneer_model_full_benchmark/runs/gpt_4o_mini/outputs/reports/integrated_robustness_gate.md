# Integrated Robustness Gate

- Recommendation: `blocked_by_robustness_regression`
- Promotion allowed: `False`

## Gates

- `strict_score_non_regression`: `False` observed `None`
- `hidden_style_passes`: `False` observed `None`
- `check_submission_ready_passes`: `False` observed `{'ok': False}`
- `endpoint_matrix_clean`: `True` observed `{}`
- `unsupported_claims_not_increased`: `True` observed `{'generated_prompt_unsupported_claim_count': None, 'generated_prompt_runtime_pass_count': None, 'generated_prompt_validation_fail_count': None}`
- `template_dependency_known_not_promoted`: `False` observed `None`
- `paraphrase_consistency_recorded`: `False` observed `None`
- `multi_llm_sensitivity_not_promoted`: `True` observed `{'llm_calls_executed': None}`
- `tool_efficiency_recorded`: `False` observed `None`
- `schema_aware_not_promoted`: `True` observed `None`
- `final_submission_format_unchanged`: `False` observed `False`
- `generated_prompt_clusters_recorded`: `False` observed `None`
- `answer_shape_trial_not_promoted_without_gate`: `False` observed `{'eligible_rows': None, 'implementation_ready': None, 'runtime_change_applied': None}`
- `route_mismatch_analysis_recorded`: `False` observed `{'mismatch_count': None, 'likely_cause_counts': None}`
- `endpoint_selection_analysis_recorded`: `False` observed `{'gap_count': None, 'gap_type_counts': None}`
- `live_efficiency_trial_not_promoted_without_strict_delta`: `False` observed `{'api_prompt_rows': None, 'runtime_change_applied': None}`
- `efficiency_recovery_trial_recorded`: `False` observed `{'best_variant': None, 'best_projected_strict_score': None, 'recommendation': None}`
- `no_template_mode_not_packaged`: `False` observed `None`
