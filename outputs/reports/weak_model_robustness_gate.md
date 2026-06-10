# Weak Model Robustness Gate

Diagnostic-only gate for weak-model scaffold lift. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.

- Recommendation: `weak_harness_balanced_improved_keep_shadow`
- Gate passed: `True`
- Small-model lift score: `0.1385`
- SQL lift: `0.12`
- Unsupported claims in best scaffold: `0`

- Weak generated prompts: `50` / `50`
- Weak paraphrase consistency: `0.8431`
- Weak no-template SQL validation: `1.0`
- Weak SQL bottleneck: `SQL_valid_but_wrong_semantics`

- Weak SQL trial best SQL variant: `weak_scaffold_answer_fallback_v3` / SQL `0.18`

- Weak harness best variant: `weak_harness_answer_and_efficiency_v2` / strict `0.2981` / SQL `0.12` / answer `0.2194`

- Weak answer-grounding v3 best: `weak_scaffold_sql_lift_api_recovery_v3` / answer `0.2359`

## Gates

- `strict_score_improves_over_raw_weak`: `True`
- `strict_score_beats_guided_weak`: `True`
- `sql_score_improves_over_raw_weak`: `True`
- `api_score_not_regressed_vs_raw_or_guided_weak`: `True`
- `answer_grounding_improves_over_previous_scaffold`: `True`
- `unsupported_claims_zero`: `True`
- `generated_prompt_runtime_pass_high`: `True`
- `weak_generated_prompt_runtime_pass_high`: `True`
- `weak_generated_prompt_validation_clean`: `True`
- `weak_generated_prompt_unsupported_claims_zero`: `True`
- `paraphrase_consistency_available_or_nonregressed`: `True`
- `weak_paraphrase_consistency_acceptable`: `True`
- `weak_no_template_unsupported_claims_zero`: `True`
- `weak_no_template_validation_acceptable`: `True`
- `weak_sql_trial_sql_improved`: `True`
- `weak_sql_trial_api_nonregression`: `True`
- `weak_sql_trial_answer_nonregression`: `True`
- `weak_answer_v3_improves_over_v2`: `True`
- `weak_answer_v3_strict_improves_over_v2`: `True`
- `weak_answer_v3_answer_nonregression_vs_v1`: `True`
- `weak_harness_sql_improved`: `True`
- `weak_harness_api_nonregression`: `True`
- `weak_harness_answer_nonregression`: `True`
- `weak_harness_unsupported_claims_zero`: `True`
- `weak_harness_bounded_or_full_gate_passed`: `True`
- `endpoint_matrix_clean`: `True`
- `hidden_style_passes`: `True`
- `token_runtime_cost_acceptable`: `True`
- `final_submission_format_unchanged`: `True`
- `packaged_runtime_unchanged`: `True`
