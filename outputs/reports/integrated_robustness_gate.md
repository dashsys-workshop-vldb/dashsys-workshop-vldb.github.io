# Integrated Robustness Gate

- Recommendation: `promote_arbitration_policy_only`
- Promotion allowed: `True`

## Gates

- `strict_score_non_regression`: `True` observed `0.6555`
- `hidden_style_passes`: `True` observed `{'failed_cases': 0, 'family_stability_rate': 1.0, 'passed_cases': 48, 'schema_stability_rate': 1.0, 'top_failure_categories': [], 'total_cases': 48}`
- `check_submission_ready_passes`: `True` observed `{'ok': True}`
- `endpoint_matrix_clean`: `True` observed `{'live_empty': 5, 'live_success': 10}`
- `unsupported_claims_not_increased`: `True` observed `no increase detected in current diagnostic reports`
- `template_dependency_known_not_promoted`: `True` observed `0.1634`
- `paraphrase_consistency_recorded`: `True` observed `0.9907`
- `multi_llm_sensitivity_not_promoted`: `True` observed `{'llm_calls_executed': 0}`
- `tool_efficiency_recorded`: `True` observed `1.4571`
- `schema_aware_not_promoted`: `True` observed `{'decision': 'keep_trial_only', 'failed_gates': ['strict_score_non_regression', 'template_dependency_decreased'], 'promotion_allowed': False, 'reason': 'Robustness gates did not all pass; schema-aware SQL remains diagnostic-only.'}`
- `final_submission_format_unchanged`: `True` observed `True`
