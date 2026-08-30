# LLM Answer Verifier Ablation

The no-verifier mode is diagnostic-only and promotion-ineligible.

## Organizer Answer Scores
| Strategy | Value |
|---|---:|
| SQL_FIRST_API_VERIFY | 0.3207 |
| ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER | 0.85 |
| ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER | 0.85 |
| ROBUST_ABLATION_ANSWER_GROUNDING_ONLY | 0.85 |
| ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER | 0.1529 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE | 0.5609 |

## Internal 500 Final Answer Correctness
| Strategy | Value |
|---|---:|
| packaged_baseline_real | 0.653 |
| ablation_llm_answer_no_verifier_real | 0.653 |
| ablation_llm_answer_with_verifier_real | 0.653 |
| ablation_answer_grounding_only_real | 0.653 |
| ablation_full_candidate_no_llm_answer_real | 0.656 |
| robust_generalized_harness_candidate_real | 0.656 |