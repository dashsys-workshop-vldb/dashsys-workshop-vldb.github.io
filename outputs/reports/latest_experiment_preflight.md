# Latest Experiment Preflight

Classification: `diagnostic_only`.

- Packaged default strategy: `SQL_FIRST_API_VERIFY`.
- Branch: `codex/schema-aware-sql-fallback`
- Git status short: `clean`
- Current strict score: `0.6621`
- SQL/API/answer: `0.9333` / `0.9791` / `0.3337`
- Hidden-style: `48/48`
- check_submission_ready ok: `True`

## Module Existence

- `dashagent/prompt_semantic_ir.py`: `True`
- `dashagent/semantic_intent_context_builder.py`: `True`
- `dashagent/semantic_intent_classifier.py`: `True`
- `dashagent/routing_anti_hallucination_gate.py`: `True`
- `dashagent/no_tool_safety_verifier.py`: `True`
- `dashagent/semantic_route_decision_ladder.py`: `True`
- `dashagent/evidence_match_scorer.py`: `True`
- `dashagent/staged_evidence_policy.py`: `True`
- `dashagent/post_sql_decision_card.py`: `True`
- `dashagent/post_sql_deterministic_policy.py`: `True`
- `dashagent/post_sql_llm_advisor.py`: `True`
- `dashagent/post_sql_api_call_verifier.py`: `True`

## Benchmark Files

- `data/benchmarks/dashagent_500_prompt_suite.jsonl`: `False`
- `data/benchmarks/dashagent_500_prompt_suite_gold.jsonl`: `False`
- `data/benchmarks/dashagent_500_prompt_suite_manifest.json`: `False`

## Prior Reports

- `semantic_routing_and_staged_evidence_policy`: `True`
- `semantic_route_decision_ladder_trial`: `True`
- `semantic_route_promotion_gate`: `True`
- `staged_evidence_policy_trial`: `True`
- `post_sql_api_decision_trial`: `True`

Benchmark missing: `True`.
No runtime behavior was changed by this preflight.
