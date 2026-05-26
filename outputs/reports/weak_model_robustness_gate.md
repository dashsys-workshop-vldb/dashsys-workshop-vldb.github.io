# Weak Model Robustness Gate

Diagnostic-only gate for weak-model scaffold lift. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.

- Recommendation: `weak_model_scaffold_candidate`
- Gate passed: `False`
- Small-model lift score: `0.0771`
- SQL lift: `0.18`
- Unsupported claims in best scaffold: `0`

## Gates

- `strict_score_improves_over_raw_weak`: `True`
- `sql_score_improves_over_raw_weak`: `True`
- `api_score_not_regressed_vs_raw_weak`: `False`
- `unsupported_claims_zero`: `True`
- `generated_prompt_runtime_pass_high`: `True`
- `paraphrase_consistency_available_or_nonregressed`: `True`
- `endpoint_matrix_clean`: `True`
- `hidden_style_passes`: `True`
- `final_submission_format_unchanged`: `True`
- `packaged_runtime_unchanged`: `True`
