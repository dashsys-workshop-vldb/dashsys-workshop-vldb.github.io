# Semantic Role-Aware Verifier Refactor

## Scope

This pass refactored the explicit `ROBUST_GENERALIZED_HARNESS_CANDIDATE` semantic routing layer so no-tool safety is based on semantic roles instead of surface keywords alone. The packaged default remains `SQL_FIRST_API_VERIFY`.

No promotion recommendation, benchmark conclusion, packaged default change, or final submission schema change is included.

## Implemented

- Added `SemanticParse` fixed JSON-compatible schema in `dashagent/semantic_parse.py`.
- Added `parse_prompt_semantics` in `dashagent/semantic_parser.py`.
- Added `SemanticConsistencyVerifier` in `dashagent/semantic_consistency_verifier.py`.
- Extended objective prompt features with factual span fields:
  - quoted spans
  - meta-language indicators
  - operation candidate spans
  - target candidate spans
  - conceptual object terms
  - data object terms
  - format request terms
- Updated the semantic route decision ladder to use:
  - objective features
  - semantic parse
  - semantic intent decision
  - routing anti-hallucination gate
  - semantic consistency verifier
  - route action
- Added candidate checkpoints:
  - `checkpoint_semantic_parse`
  - `checkpoint_semantic_consistency_verifier`

## Keyword-Only Blocking Removed

The candidate no longer treats words like `list`, `schema`, `inactive`, or `journey` as automatic evidence requirements. The verifier now checks whether the semantic parse says the prompt is a conceptual/meta-language/out-of-domain request or a supported instance-level data request.

Examples:

- `List three reasons why schemas matter.` is parsed as a conceptual format request with `evidence_need=NONE`.
- `List current schemas in the sandbox.` is parsed as a supported data-object retrieval with evidence required.
- `What does 'inactive journey' mean?` is parsed as conceptual/meta-language, not a status lookup.
- `Show inactive journeys.` is parsed as an instance-level data/status lookup.
- `In the phrase 'list schemas', what does 'list' mean?` is parsed as meta-language.

## Validation

- `python3 -m pytest -q tests/test_semantic_parse_and_verifier.py tests/test_robust_generalized_candidate.py`: `20 passed`
- `python3 scripts/run_one_query.py "List three reasons why schemas matter." --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id semantic_parse_no_tool_smoke`: passed, `tool_call_count=0`
- `python3 scripts/run_one_query.py "List current schemas in the sandbox." --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id semantic_parse_data_smoke`: passed, `tool_call_count=2`
- `python3 scripts/check_submission_ready.py`: `ok=true`, default remains `SQL_FIRST_API_VERIFY`
- `git diff --check`: passed

## Known TODOs

- Evaluate direct conceptual answer rendering quality in a later pass; the smoke test here verifies routing/tool behavior only.
- Run broader candidate benchmarks only in a later evaluation pass.
- Keep the LLM semantic parser path behind explicit candidate configuration until backend availability and latency are measured.
