# Real Behavior Change Error Analysis

## robust_generalized_harness_candidate_real
- helped_count: 86
- hurt_count: 48
- helped_categories: {'api_call_saved_without_answer_loss': 57, 'conceptual_false_positive_tool_call_avoided': 29}
- hurt_categories: {'api_called_unnecessarily': 10, 'wrong_no_tool_skip': 38}

## ablation_no_semantic_routing_real
- helped_count: 21
- hurt_count: 0
- helped_categories: {'api_call_saved_without_answer_loss': 21}
- hurt_categories: {}

## ablation_semantic_routing_only_real
- helped_count: 69
- hurt_count: 48
- helped_categories: {'api_call_saved_without_answer_loss': 40, 'conceptual_false_positive_tool_call_avoided': 29}
- hurt_categories: {'api_called_unnecessarily': 10, 'wrong_no_tool_skip': 38}

## ablation_staged_evidence_only_real
- helped_count: 21
- hurt_count: 0
- helped_categories: {'api_call_saved_without_answer_loss': 21}
- hurt_categories: {}

## ablation_answer_grounding_only_real
- helped_count: 0
- hurt_count: 0
- helped_categories: {}
- hurt_categories: {}

## ablation_llm_answer_no_verifier_real
- helped_count: 0
- hurt_count: 0
- helped_categories: {}
- hurt_categories: {}

## ablation_llm_answer_with_verifier_real
- helped_count: 0
- hurt_count: 0
- helped_categories: {}
- hurt_categories: {}

## ablation_semantic_role_parse_only_real
- helped_count: 59
- hurt_count: 38
- helped_categories: {'api_call_saved_without_answer_loss': 40, 'conceptual_false_positive_tool_call_avoided': 19}
- hurt_categories: {'wrong_no_tool_skip': 38}

## ablation_no_llm_components_real
- helped_count: 86
- hurt_count: 48
- helped_categories: {'api_call_saved_without_answer_loss': 57, 'conceptual_false_positive_tool_call_avoided': 29}
- hurt_categories: {'api_called_unnecessarily': 10, 'wrong_no_tool_skip': 38}

## ablation_full_candidate_no_llm_answer_real
- helped_count: 86
- hurt_count: 48
- helped_categories: {'api_call_saved_without_answer_loss': 57, 'conceptual_false_positive_tool_call_avoided': 29}
- hurt_categories: {'api_called_unnecessarily': 10, 'wrong_no_tool_skip': 38}

## ablation_full_candidate_no_safe_api_probe_real
- helped_count: 76
- hurt_count: 38
- helped_categories: {'api_call_saved_without_answer_loss': 57, 'conceptual_false_positive_tool_call_avoided': 19}
- hurt_categories: {'wrong_no_tool_skip': 38}

## ablation_full_candidate_no_staged_policy_real
- helped_count: 69
- hurt_count: 48
- helped_categories: {'api_call_saved_without_answer_loss': 40, 'conceptual_false_positive_tool_call_avoided': 29}
- hurt_categories: {'api_called_unnecessarily': 10, 'wrong_no_tool_skip': 38}

## ablation_full_candidate_no_semantic_parse_real
- helped_count: 64
- hurt_count: 219
- helped_categories: {'api_call_saved_without_answer_loss': 4, 'conceptual_false_positive_tool_call_avoided': 28, 'trace_process_or_behavior_alignment_improved': 32}
- hurt_categories: {'api_called_unnecessarily': 90, 'final_answer_omitted_evidence': 122, 'no_clear_failure': 7}
