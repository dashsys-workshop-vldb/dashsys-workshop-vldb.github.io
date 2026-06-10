# score075 Candidate Generation Handoff

This worker stayed within candidate-generation ownership and did not edit runtime execution, scoring, or final submission paths.

## Declared Dependencies

- local_index: api_missing_blocked via `codex/score075-local-index`
- endpoint_routing: api_available_declared_dependency via `codex/score075-endpoint-routing`
- answer_shape: api_missing_blocked via `codex/score075-answer-shape`

## Requested Dependency APIs

- local-index: provide Parquet-derived evidence objects as `local_index_evidence` for `generate_targeted_candidates`.
- endpoint-routing: provide leakage-safe rule dictionaries as `endpoint_rule_candidates`.
- answer-shape: provide shape hints as `answer_shape_hints`; candidates will not change answers directly.

## Safety Notes

- Candidate triggers must remain reusable and cannot depend on query_id or exact full public query strings.
- Local index evidence must be provenance-tagged and must not contain final answers.
- This branch recommends selector/integration evaluation only; it does not promote behavior.
