# Weak Model Robustness Gate

Diagnostic-only gate for weak-model scaffold lift. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.

- Recommendation: `weak_model_scaffold_improved_keep_shadow`
- Gate passed: `True`
- Small-model lift score: `0.1277`
- SQL lift: `0.06`
- Unsupported claims in best scaffold: `0`

## Gates

- `strict_score_improves_over_raw_weak`: `True`
- `strict_score_beats_guided_weak`: `True`
- `sql_score_improves_over_raw_weak`: `True`
- `api_score_not_regressed_vs_raw_or_guided_weak`: `True`
- `answer_grounding_improves_over_previous_scaffold`: `True`
- `unsupported_claims_zero`: `True`
- `generated_prompt_runtime_pass_high`: `True`
- `paraphrase_consistency_available_or_nonregressed`: `True`
- `endpoint_matrix_clean`: `True`
- `hidden_style_passes`: `True`
- `token_runtime_cost_acceptable`: `True`
- `final_submission_format_unchanged`: `True`
- `packaged_runtime_unchanged`: `True`
