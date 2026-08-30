# Robust Generalized Focused Stress Ablation

- cases: `19`

| Mode | no_tool_false_positive | no_tool_false_negative | api_required_underuse | unsupported_claims | llm_answer_verifier_blocked_claims | llm_answer_rewrite_success | llm_answer_fallback_used | sql_calls | api_calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ROBUST_ABLATION_ANSWER_GROUNDING_ONLY | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SAFE_API_PROBE | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_SEMANTIC_PARSE | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 6 | 18 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_STAGED_POLICY | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |
| ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |
| ROBUST_ABLATION_NO_LLM_COMPONENTS | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_NO_SEMANTIC_ROUTING | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |
| ROBUST_ABLATION_SEMANTIC_ROLE_PARSE_ONLY | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_SEMANTIC_ROUTING_ONLY | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| ROBUST_ABLATION_STAGED_EVIDENCE_ONLY | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 9 |
| SQL_FIRST_API_VERIFY | 0 | 5 | 1 | 0 | 0 | 0 | 0 | 16 | 12 |