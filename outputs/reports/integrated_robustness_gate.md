# Integrated Robustness Gate

- Recommendation: `blocked_by_robustness_regression`
- Promotion allowed: `False`

## Gates

- `strict_score_non_regression`: `False` observed `0.6513`
- `hidden_style_passes`: `True` observed `{'failed_cases': 0, 'family_stability_rate': 1.0, 'passed_cases': 48, 'schema_stability_rate': 1.0, 'top_failure_categories': [], 'total_cases': 48}`
- `check_submission_ready_passes`: `True` observed `{'ok': True}`
- `endpoint_matrix_clean`: `True` observed `{'live_empty': 5, 'live_success': 10}`
- `unsupported_claims_not_increased`: `True` observed `{'generated_prompt_unsupported_claim_count': 0, 'generated_prompt_runtime_pass_count': 250, 'generated_prompt_validation_fail_count': 0}`
- `template_dependency_known_not_promoted`: `True` observed `0.1634`
- `paraphrase_consistency_recorded`: `True` observed `0.9907`
- `multi_llm_sensitivity_not_promoted`: `True` observed `{'llm_calls_executed': 0}`
- `tool_efficiency_recorded`: `True` observed `1.4571`
- `schema_aware_not_promoted`: `True` observed `{'decision': 'keep_trial_only', 'failed_gates': ['strict_score_non_regression', 'template_dependency_decreased'], 'promotion_allowed': False, 'reason': 'Robustness gates did not all pass; schema-aware SQL remains diagnostic-only.'}`
- `final_submission_format_unchanged`: `True` observed `True`
- `generated_prompt_clusters_recorded`: `True` observed `{'answer_shape_weak': 88, 'api_endpoint_selection_gap': 57, 'no_clear_failure': 17, 'no_template_fallback_weak': 2, 'route_mismatch': 86}`
- `answer_shape_trial_not_promoted_without_gate`: `True` observed `{'eligible_rows': 141, 'implementation_ready': False, 'runtime_change_applied': False}`
- `route_mismatch_analysis_recorded`: `True` observed `{'mismatch_count': 86, 'likely_cause_counts': {'ambiguous_domain_terms': 44, 'api_need_decision_gap': 33, 'generated_label_noise': 3, 'no_template_fallback_route_gap': 4, 'unnecessary_api_call_noise': 2}}`
- `endpoint_selection_analysis_recorded`: `True` observed `{'gap_count': 152, 'gap_type_counts': {'less_useful_or_error_endpoint_selected': 138, 'optional_api_call_when_sql_complete': 14}}`
- `live_efficiency_trial_not_promoted_without_strict_delta`: `True` observed `{'api_prompt_rows': 202, 'runtime_change_applied': False}`
- `efficiency_recovery_trial_recorded`: `True` observed `{'best_variant': 'compact_repeated_checkpoint_metadata', 'best_projected_strict_score': 0.6575, 'recommendation': 'promote_efficiency_recovery_fix'}`
- `no_template_mode_not_packaged`: `True` observed `{'promotable': False, 'reason': 'Template-disabled behavior is not evaluated as packaged runtime; schema-aware fallback must pass separate strict and robustness gates before any promotion.'}`
