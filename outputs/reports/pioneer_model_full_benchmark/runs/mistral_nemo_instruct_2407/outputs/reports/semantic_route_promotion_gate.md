# Semantic Route Promotion Gate

Classification: `diagnostic_only`.

Recommendation: `blocked_by_context_cost`.

Promotion is not allowed by this pass. The semantic routing harness remains shadow-only and the packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Gates

- public_dev_strict_no_regression: `False`
- hidden_style_passes: `False`
- check_submission_ready_passes: `False`
- generated_prompt_unsupported_claims_zero: `True`
- no_concrete_data_plain_llm_direct: `True`
- conceptual_keyword_prompts_skip_tools_safely: `False`
- tool_runtime_token_cost_improves_or_stable: `False`
- endpoint_matrix_clean: `True`
- shadow_false_positive_reduction: `False`
- no_increase_false_no_tool_risk: `True`
- packaged_runtime_unchanged: `True`
- final_submission_format_unchanged: `True`
- broad_semantic_router_promotion_blocked: `True`

## Trial Summary

- total_prompts: `None`
- action_distribution: `None`
- false_no_tool_risk_count: `None`
- conceptual_false_positive_tool_routes_reduced: `None`
- estimated_tool_call_savings: `None`
- average_context_token_cost: `None`
- average_tier_used: `None`
- recommendation: `None`
