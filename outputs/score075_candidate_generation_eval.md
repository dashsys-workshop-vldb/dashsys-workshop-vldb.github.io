# score075 Candidate Generation Eval

- Branch: `codex/score075-candidate-generation`
- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Target rows: 10
- Total candidates: 34
- Leakage failures: 0
- Packaged execution changed: False
- Merge recommendation: `candidate_generation_ready_for_selector`

## Candidate Family Counts

- answer_shape: 10
- api_first: 2
- ast_clean: 1
- baseline: 10
- endpoint_rerank: 10
- sql_first: 1

## Dependency Status

- local_index: api_missing_blocked (codex/score075-local-index)
- endpoint_routing: api_available_declared_dependency (codex/score075-endpoint-routing)
- answer_shape: api_missing_blocked (codex/score075-answer-shape)

## Rows

- example_017: 4 candidates; families=answer_shape, api_first, baseline, endpoint_rerank
- example_030: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_031: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_029: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_019: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_028: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_025: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_024: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_020: 3 candidates; families=answer_shape, baseline, endpoint_rerank
- example_021: 6 candidates; families=answer_shape, api_first, ast_clean, baseline, endpoint_rerank, sql_first
