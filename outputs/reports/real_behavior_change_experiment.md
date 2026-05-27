# Real Behavior Change Experiment

- prompt_count: 500
- grading_type: heuristic_internal_gold
- organizer_equivalent: False

## Modes
### robust_generalized_harness_candidate_real
- available: True
- behavior_score: 0.811
- trace_observability_score: 0.386
- combined_diagnostic_score: 0.7292
- final_answer_correctness: 0.656
- sql_calls: 306
- api_calls: 257
- api_calls_saved: 17
- unsupported_claims: 0
- behavior_score_delta: 0.0065
- rows_helped/hurt/neutral: 86/48/366

### ablation_no_semantic_routing_real
- available: True
- behavior_score: 0.8089
- trace_observability_score: 0.3743
- combined_diagnostic_score: 0.716
- final_answer_correctness: 0.6583
- sql_calls: 393
- api_calls: 306
- api_calls_saved: 21
- unsupported_claims: 0
- behavior_score_delta: 0.0044
- rows_helped/hurt/neutral: 21/0/479

### ablation_semantic_routing_only_real
- available: True
- behavior_score: 0.8075
- trace_observability_score: 0.3058
- combined_diagnostic_score: 0.7171
- final_answer_correctness: 0.6518
- sql_calls: 306
- api_calls: 274
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.003
- rows_helped/hurt/neutral: 69/48/383

### ablation_staged_evidence_only_real
- available: True
- behavior_score: 0.8089
- trace_observability_score: 0.3743
- combined_diagnostic_score: 0.716
- final_answer_correctness: 0.6583
- sql_calls: 393
- api_calls: 306
- api_calls_saved: 21
- unsupported_claims: 0
- behavior_score_delta: 0.0044
- rows_helped/hurt/neutral: 21/0/479

### ablation_answer_grounding_only_real
- available: True
- behavior_score: 0.8045
- trace_observability_score: 0.2495
- combined_diagnostic_score: 0.6995
- final_answer_correctness: 0.653
- sql_calls: 393
- api_calls: 327
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.0
- rows_helped/hurt/neutral: 0/0/500

### ablation_llm_answer_no_verifier_real
- available: True
- behavior_score: 0.8045
- trace_observability_score: 0.2495
- combined_diagnostic_score: 0.6995
- final_answer_correctness: 0.653
- sql_calls: 393
- api_calls: 327
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.0
- rows_helped/hurt/neutral: 0/0/500

### ablation_llm_answer_with_verifier_real
- available: True
- behavior_score: 0.8045
- trace_observability_score: 0.2495
- combined_diagnostic_score: 0.6995
- final_answer_correctness: 0.653
- sql_calls: 393
- api_calls: 327
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.0
- rows_helped/hurt/neutral: 0/0/500

### ablation_semantic_role_parse_only_real
- available: True
- behavior_score: 0.8116
- trace_observability_score: 0.326
- combined_diagnostic_score: 0.7252
- final_answer_correctness: 0.6567
- sql_calls: 326
- api_calls: 264
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.0071
- rows_helped/hurt/neutral: 59/38/403

### ablation_no_llm_components_real
- available: True
- behavior_score: 0.811
- trace_observability_score: 0.386
- combined_diagnostic_score: 0.7292
- final_answer_correctness: 0.656
- sql_calls: 306
- api_calls: 257
- api_calls_saved: 17
- unsupported_claims: 0
- behavior_score_delta: 0.0065
- rows_helped/hurt/neutral: 86/48/366

### ablation_full_candidate_no_llm_answer_real
- available: True
- behavior_score: 0.811
- trace_observability_score: 0.386
- combined_diagnostic_score: 0.7292
- final_answer_correctness: 0.656
- sql_calls: 306
- api_calls: 257
- api_calls_saved: 17
- unsupported_claims: 0
- behavior_score_delta: 0.0065
- rows_helped/hurt/neutral: 86/48/366

### ablation_full_candidate_no_safe_api_probe_real
- available: True
- behavior_score: 0.8152
- trace_observability_score: 0.4265
- combined_diagnostic_score: 0.739
- final_answer_correctness: 0.661
- sql_calls: 326
- api_calls: 247
- api_calls_saved: 17
- unsupported_claims: 0
- behavior_score_delta: 0.0107
- rows_helped/hurt/neutral: 76/38/386

### ablation_full_candidate_no_staged_policy_real
- available: True
- behavior_score: 0.8075
- trace_observability_score: 0.3058
- combined_diagnostic_score: 0.7171
- final_answer_correctness: 0.6518
- sql_calls: 306
- api_calls: 274
- api_calls_saved: 0
- unsupported_claims: 0
- behavior_score_delta: 0.003
- rows_helped/hurt/neutral: 69/48/383

### ablation_full_candidate_no_semantic_parse_real
- available: True
- behavior_score: 0.7642
- trace_observability_score: 0.3317
- combined_diagnostic_score: 0.5877
- final_answer_correctness: 0.5663
- sql_calls: 120
- api_calls: 445
- api_calls_saved: 4
- unsupported_claims: 0
- behavior_score_delta: -0.0403
- rows_helped/hurt/neutral: 64/219/217
