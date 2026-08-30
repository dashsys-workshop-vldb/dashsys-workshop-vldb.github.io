# Next Robustness Improvement Preflight

This preflight snapshots the current correctness, efficiency, generalization, live API, and packaging status before any robustness-first change.

- Current branch: `codex/schema-aware-sql-fallback`
- Current strict score: `0.6555`
- Hidden-style: `{'passed_cases': 48, 'total_cases': 48, 'failed_cases': 0, 'family_stability_rate': 1.0, 'schema_stability_rate': 1.0}`
- check_submission_ready: `{'ok': True, 'query_output_count': 73, 'default_strategy_is_sql_first_api_verify': True}`
- Endpoint matrix: `{'attempted': 15, 'success_count': 15, 'live_empty_count': 5, 'failure_count': 0, 'outcome_counts': {'live_empty': 5, 'live_success': 10}, 'status': 'complete'}`
- Generated prompt suite: `{'total_prompts': 250, 'executed_prompts': 250, 'runtime_pass_count': 250, 'runtime_fail_count': 0, 'validation_fail_count': 0, 'unsupported_claim_count': 0, 'live_api_calls': 212, 'live_success_count': 65, 'live_empty_count': 8, 'api_error_count': 139, 'top_failure_categories': {'answer_shape_weak': 88, 'api_endpoint_selection_gap': 57, 'no_clear_failure': 17, 'no_template_fallback_weak': 2, 'route_mismatch': 86}}`
- Robustness gate recommendation: `diagnose_before_runtime_change`

## Next Focus

- answer_shape_weak cluster analysis
- route mismatch root-cause analysis
- API endpoint selection gap analysis
- live API evidence/token compression trial
- no-template SQL robustness diagnostic
