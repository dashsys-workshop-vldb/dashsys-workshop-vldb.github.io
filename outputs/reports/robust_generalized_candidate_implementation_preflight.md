# Robust Generalized Candidate Implementation Preflight

- Packaged default strategy: `SQL_FIRST_API_VERIFY`
- Default remains SQL_FIRST_API_VERIFY: `true`
- Candidate currently present: `false`
- check_submission_ready ok: `true`
- query output count: `73`

## Existing Modules
- `dashagent/prompt_semantic_ir.py`: `true`
- `dashagent/semantic_intent_context_builder.py`: `true`
- `dashagent/semantic_intent_classifier.py`: `true`
- `dashagent/routing_anti_hallucination_gate.py`: `true`
- `dashagent/no_tool_safety_verifier.py`: `true`
- `dashagent/semantic_route_decision_ladder.py`: `true`
- `dashagent/staged_evidence_policy.py`: `true`
- `dashagent/post_sql_deterministic_policy.py`: `true`
- `dashagent/post_sql_llm_advisor.py`: `true`
- `dashagent/post_sql_api_call_verifier.py`: `true`
- `dashagent/evidence_bus.py`: `true`
- `dashagent/answer_slots.py`: `true`
- `dashagent/answer_slot_renderer.py`: `false`
- `dashagent/evidence_grounded_answer_builder.py`: `false`
- `dashagent/evidence_quality_classifier.py`: `false`
- `dashagent/score_provenance.py`: `true`

## Strategy Lists

- STRATEGIES: `SQL_ONLY_BASELINE, LLM_FREE_AGENT_BASELINE, DETERMINISTIC_ROUTER_SELECTED_METADATA, SQL_FIRST_API_VERIFY, TEMPLATE_FIRST`
- APPLIED_TRIAL_STRATEGIES: `STAGED_EVIDENCE_APPLIED_TRIAL, POST_SQL_DETERMINISTIC_APPLIED_TRIAL, COMBINED_SAFE_APPLIED_TRIAL, COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`
