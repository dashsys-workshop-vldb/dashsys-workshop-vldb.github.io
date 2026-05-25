# Schema-Aware SQL Feedback Loop

Higher score is not considered meaningful unless robustness and generalization gates pass.

- Decision: `keep_trial_only`
- Promotion allowed: `False`
- Strict score delta: `-0.016`
- Template dependency score: `0.1634`
- Paraphrase consistency score: `0.9907`
- LLM calls executed: `0`

## Promotion Gates

- `strict_score_non_regression`: passed `False`, observed `-0.016`
- `hidden_style_48_of_48`: passed `True`, observed `{'passed': 48, 'total': 48, 'failed': 0}`
- `paraphrase_consistency_stable`: passed `True`, observed `0.9907`
- `template_dependency_decreased`: passed `False`, observed `0.1634`
- `unsafe_sql_no_increase`: passed `True`, observed `0`
- `unsupported_claims_no_increase`: passed `True`, observed `not_changed_answer_path`
- `tool_runtime_no_significant_regression`: passed `True`, observed `{'tool_count_delta': 0.0, 'runtime_delta': -0.0006}`
- `multi_backend_or_no_llm_robustness`: passed `True`, observed `{'llm_calls_executed': 0, 'available_backend_count': 4}`
- `coverage_report_available`: passed `True`, observed `285`
