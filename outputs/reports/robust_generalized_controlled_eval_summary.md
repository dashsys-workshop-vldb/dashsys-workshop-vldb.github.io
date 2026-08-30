# Robust Generalized Controlled Eval Summary

- packaged_default_strategy: `SQL_FIRST_API_VERIFY`
- packaged_default_unchanged: `True`
- promotion_judgment: `not_run`

## Organizer 35
| Mode | final_score | correctness | sql_score | api_score | answer_score | api_required_underuse |
|---|---:|---:|---:|---:|---:|---:|
| ROBUST_ABLATION_ANSWER_GROUNDING_ONLY | 0.8882 | 0.9172 | 0.9333 | 0.9791 | 0.85 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER | 0.5093 | 0.5342 | 0.9333 | 0.7908 | 0.1529 | 2 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SAFE_API_PROBE | 0.839 | 0.8671 | 0.9333 | 0.9146 | 0.8069 | 2 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SEMANTIC_PARSE | 0.4155 | 0.4369 | 0.3667 | 0.6918 | 0.2656 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_STAGED_POLICY | 0.6628 | 0.6893 | 0.9333 | 0.7908 | 0.5609 | 2 |
| ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER | 0.8882 | 0.9172 | 0.9333 | 0.9791 | 0.85 | 0 |
| ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER | 0.8884 | 0.9172 | 0.9333 | 0.9791 | 0.85 | 0 |
| ROBUST_ABLATION_NO_LLM_COMPONENTS | 0.5094 | 0.5342 | 0.9333 | 0.7908 | 0.1529 | 2 |
| ROBUST_ABLATION_NO_SEMANTIC_ROUTING | 0.888 | 0.9172 | 0.9333 | 0.9791 | 0.85 | 0 |
| ROBUST_ABLATION_SEMANTIC_ROLE_PARSE_ONLY | 0.6294 | 0.6551 | 0.9333 | 0.9146 | 0.3181 | 2 |
| ROBUST_ABLATION_SEMANTIC_ROUTING_ONLY | 0.551 | 0.576 | 0.9333 | 0.7908 | 0.2695 | 2 |
| ROBUST_ABLATION_STAGED_EVIDENCE_ONLY | 0.6584 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 0 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE | 0.6628 | 0.6893 | 0.9333 | 0.7908 | 0.5609 | 2 |
| SQL_FIRST_API_VERIFY | 0.6578 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 0 |

## Internal 500
| Mode | behavior_score | final_answer_correctness | combined_diagnostic_score | unsupported_claims | api_required_underuse |
|---|---:|---:|---:|---:|---:|
| ablation_answer_grounding_only_real | 0.8045 | 0.653 | 0.6995 | 0 | 0 |
| ablation_full_candidate_no_llm_answer_real | 0.811 | 0.656 | 0.7292 | 0 | 0 |
| ablation_full_candidate_no_safe_api_probe_real | 0.8152 | 0.661 | 0.739 | 0 | 0 |
| ablation_full_candidate_no_semantic_parse_real | 0.7642 | 0.5663 | 0.5877 | 0 | 0 |
| ablation_full_candidate_no_staged_policy_real | 0.8075 | 0.6518 | 0.7171 | 0 | 0 |
| ablation_llm_answer_no_verifier_real | 0.8045 | 0.653 | 0.6995 | 0 | 0 |
| ablation_llm_answer_with_verifier_real | 0.8045 | 0.653 | 0.6995 | 0 | 0 |
| ablation_no_llm_components_real | 0.811 | 0.656 | 0.7292 | 0 | 0 |
| ablation_no_semantic_routing_real | 0.8089 | 0.6583 | 0.716 | 0 | 0 |
| ablation_semantic_role_parse_only_real | 0.8116 | 0.6567 | 0.7252 | 0 | 0 |
| ablation_semantic_routing_only_real | 0.8075 | 0.6518 | 0.7171 | 0 | 0 |
| ablation_staged_evidence_only_real | 0.8089 | 0.6583 | 0.716 | 0 | 0 |
| packaged_baseline_real | 0.8045 | 0.653 | 0.6995 | 0 | 0 |
| robust_generalized_harness_candidate_real | 0.811 | 0.656 | 0.7292 | 0 | 0 |

## Focused Stress
| Mode | no_tool_false_positive | no_tool_false_negative | api_required_underuse | unsupported_claims |
|---|---:|---:|---:|---:|
| ROBUST_ABLATION_ANSWER_GROUNDING_ONLY | 0 | 5 | 1 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SAFE_API_PROBE | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SEMANTIC_PARSE | 0 | 5 | 0 | 0 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_STAGED_POLICY | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER | 0 | 5 | 1 | 0 |
| ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER | 0 | 5 | 1 | 0 |
| ROBUST_ABLATION_NO_LLM_COMPONENTS | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_NO_SEMANTIC_ROUTING | 0 | 5 | 1 | 0 |
| ROBUST_ABLATION_SEMANTIC_ROLE_PARSE_ONLY | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_SEMANTIC_ROUTING_ONLY | 0 | 0 | 1 | 0 |
| ROBUST_ABLATION_STAGED_EVIDENCE_ONLY | 0 | 5 | 1 | 0 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE | 0 | 0 | 1 | 0 |
| SQL_FIRST_API_VERIFY | 0 | 5 | 1 | 0 |

## Post-Run Validation Refresh

- Hardcode/runtime leakage audit: `unsafe_runtime_hardcode_count=0`, `unsafe_fake_score_count=0`, `runtime_leakage_detected=false`, `promotion_eligible_simulated_trace=false`
- Score provenance audit: `runtime_gold_visible_count=0`, `real_agent_execution_reports=3`, `promotion_ineligible_simulated_reports=1`
- Targeted secret scan: `clean`; raw regex hits were limited to synthetic test fixtures and packaging marker strings.
- Validation: `check_submission_ready`, `hidden_style`, `audit_workshop_requirements`, `generate_sdk_usage_audit`, `pytest`, and `git diff --check` passed after the audit classifier refresh.

This report is diagnostic-only and intentionally does not recommend promotion.
