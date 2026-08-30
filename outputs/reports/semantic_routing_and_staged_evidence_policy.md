# Semantic Routing and Staged Evidence Policy

Classification: `diagnostic_only`. All behavior is shadow-only; packaged `SQL_FIRST_API_VERIFY` execution and final submission format are unchanged.

## Summary

- decision_ladder_action_distribution: `{'EVIDENCE_PIPELINE': 92, 'LLM_DIRECT': 5, 'SAFE_API_PROBE': 1}`
- routing_anti_hallucination_feedback_loop_statistics: `{'initial_pass': 98, 'initial_fail': 0, 'revision_attempts': 0, 'revision_success': 0, 'revision_fail': 0, 'fallback_counts': {}}`
- no_tool_safety_verifier_statistics: `{'allowed': 5, 'blocked': 93, 'false_no_tool_risk': 0}`
- initial_evidence_branch_distribution: `{'API': 11, 'SQL': 74}`
- post_sql_deterministic_policy_distribution: `{'AMBIGUOUS': 2, 'CALL_API': 19, 'CAVEAT_ONLY': 7, 'SKIP_API': 7}`
- llm_post_sql_advisor_invocation_count: `9`
- llm_advice_verified_count: `0`
- llm_advice_blocked_count: `0`
- api_calls_saved: `15`
- api_calls_added: `0`
- false_no_tool_risk: `0`
- endpoint_matrix_status: `unchanged_shadow_only`
- promotion_recommendation: `keep_shadow_only`
