# Real Behavior Change Gate

- recommendation: blocked_by_no_tool_false_positive
- packaged_runtime_changed: False
- final_submission_format_changed: False

## robust_generalized_harness_candidate_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive', 'runtime_cost']

## ablation_no_semantic_routing_real
- passed: False
- recommendation: blocked_by_runtime_cost
- blockers: ['runtime_cost']

## ablation_semantic_routing_only_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive']

## ablation_staged_evidence_only_real
- passed: True
- recommendation: keep_shadow_only
- blockers: []

## ablation_answer_grounding_only_real
- passed: False
- recommendation: blocked_by_runtime_cost
- blockers: ['runtime_cost']

## ablation_llm_answer_no_verifier_real
- passed: False
- recommendation: blocked_by_runtime_cost
- blockers: ['runtime_cost']

## ablation_llm_answer_with_verifier_real
- passed: False
- recommendation: blocked_by_runtime_cost
- blockers: ['runtime_cost']

## ablation_semantic_role_parse_only_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive']

## ablation_no_llm_components_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive']

## ablation_full_candidate_no_llm_answer_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive']

## ablation_full_candidate_no_safe_api_probe_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive', 'runtime_cost']

## ablation_full_candidate_no_staged_policy_real
- passed: False
- recommendation: blocked_by_no_tool_false_positive
- blockers: ['no_tool_false_positive', 'runtime_cost']

## ablation_full_candidate_no_semantic_parse_real
- passed: False
- recommendation: blocked_by_runtime_cost
- blockers: ['behavior_regression', 'final_answer_regression', 'runtime_cost']
