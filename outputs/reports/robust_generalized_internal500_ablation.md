# Robust Generalized Internal 500 Ablation

- status: `completed`
- prompt_count: `500`

| Mode | behavior_score | final_answer_correctness | trace_observability_score | combined_diagnostic_score | unsupported_claims | no_tool_false_positive | api_required_underuse | sql_calls | api_calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ablation_answer_grounding_only_real | 0.8045 | 0.653 | 0.2495 | 0.6995 | 0 | 0 | 0 | 393 | 327 |
| ablation_full_candidate_no_llm_answer_real | 0.811 | 0.656 | 0.386 | 0.7292 | 0 | 38 | 0 | 306 | 257 |
| ablation_full_candidate_no_safe_api_probe_real | 0.8152 | 0.661 | 0.4265 | 0.739 | 0 | 38 | 0 | 326 | 247 |
| ablation_full_candidate_no_semantic_parse_real | 0.7642 | 0.5663 | 0.3317 | 0.5877 | 0 | 0 | 0 | 120 | 445 |
| ablation_full_candidate_no_staged_policy_real | 0.8075 | 0.6518 | 0.3058 | 0.7171 | 0 | 38 | 0 | 306 | 274 |
| ablation_llm_answer_no_verifier_real | 0.8045 | 0.653 | 0.2495 | 0.6995 | 0 | 0 | 0 | 393 | 327 |
| ablation_llm_answer_with_verifier_real | 0.8045 | 0.653 | 0.2495 | 0.6995 | 0 | 0 | 0 | 393 | 327 |
| ablation_no_llm_components_real | 0.811 | 0.656 | 0.386 | 0.7292 | 0 | 38 | 0 | 306 | 257 |
| ablation_no_semantic_routing_real | 0.8089 | 0.6583 | 0.3743 | 0.716 | 0 | 0 | 0 | 393 | 306 |
| ablation_semantic_role_parse_only_real | 0.8116 | 0.6567 | 0.326 | 0.7252 | 0 | 38 | 0 | 326 | 264 |
| ablation_semantic_routing_only_real | 0.8075 | 0.6518 | 0.3058 | 0.7171 | 0 | 38 | 0 | 306 | 274 |
| ablation_staged_evidence_only_real | 0.8089 | 0.6583 | 0.3743 | 0.716 | 0 | 0 | 0 | 393 | 306 |
| packaged_baseline_real | 0.8045 | 0.653 | 0.2495 | 0.6995 | 0 | 0 | 0 | 393 | 327 |
| robust_generalized_harness_candidate_real | 0.811 | 0.656 | 0.386 | 0.7292 | 0 | 38 | 0 | 306 | 257 |

This is internal heuristic gold, not organizer-equivalent.