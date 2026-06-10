# Semantic Route Promotion Gate

Classification: `diagnostic_only`.

Recommendation: `keep_shadow_only`.

Promotion is not allowed by this pass. The semantic routing harness remains shadow-only and the packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Gates

- public_dev_strict_no_regression: `False`
- hidden_style_passes: `True`
- check_submission_ready_passes: `True`
- generated_prompt_unsupported_claims_zero: `True`
- no_concrete_data_plain_llm_direct: `True`
- conceptual_keyword_prompts_skip_tools_safely: `True`
- tool_runtime_token_cost_improves_or_stable: `True`
- endpoint_matrix_clean: `True`
- shadow_false_positive_reduction: `True`
- no_increase_false_no_tool_risk: `True`
- packaged_runtime_unchanged: `True`
- final_submission_format_unchanged: `True`
- broad_semantic_router_promotion_blocked: `True`

## Trial Summary

- total_prompts: `98`
- action_distribution: `{'EVIDENCE_PIPELINE': 92, 'LLM_DIRECT': 5, 'SAFE_API_PROBE': 1}`
- false_no_tool_risk_count: `0`
- conceptual_false_positive_tool_routes_reduced: `5`
- estimated_tool_call_savings: `6`
- average_context_token_cost: `233.52`
- average_tier_used: `0.01`
- recommendation: `keep_shadow_only`
