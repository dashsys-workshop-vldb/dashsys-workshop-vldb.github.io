# Final Answer Evidence Use Fix

## Objective

Fix V2 SDK-toolcall Semantic IR final-answer behavior so available local/runtime evidence is answered directly, and failed live/API sources are represented as scoped caveats instead of collapsing the entire answer to runtime unavailable.

## Implementation Result

- Unified Planner facade restored: `true`
- SDK-toolcall Semantic IR primary: `true`
- Free-form SQL/API avoided: `true`
- Atomic protocol fallback used: `0`
- Backend semantic planning used: `false`
- Packaged default changed: `false`

## Code Changes

- `dashagent/llm_final_answer_composer.py`
  - Added explicit `AVAILABLE_RUNTIME_FACTS` to the final-answer card.
  - Added explicit `FAILED_OR_UNAVAILABLE_SOURCES` to the final-answer card.
  - Strengthened final-answer instructions for partial local evidence plus failed live/API evidence.
  - Made safe fallback evidence-aware: if facts exist, fallback summarizes scoped evidence instead of using global unavailable.
  - Stopped requiring DIRECT concept passes as runtime evidence pass IDs.
  - Allowed broad inventory summaries with count plus sample names for prompts like `What schemas do I have?`.
- `dashagent/final_answer_claim_extractor.py`
  - Stopped treating numbered-list markers such as `1.` and `2.` as count claims.
- `dashagent/v2_semantic_ir_validator.py`
  - Added structural validation that local COUNT tasks must include `LOCAL_QUERY` with `local_query.count=true`.
- `dashagent/v2_semantic_ir_planner.py`
  - Added prompt guidance forbidding sampled-list aggregation for requested count answers.
- `scripts/run_hermes_v2_toolcall_smoke.py`
  - Added `final_answer_repair_attempts`, `repaired_success`, and `final_unavailable_with_runtime_facts` metrics.

## Latest Hermes V2 Toolcall Smoke

- ok: `true`
- passed_count: `7`
- failed_count: `0`
- runtime_fact_count: `8`
- local_snapshot_fact_count: `8`
- live_api_fact_count: `0`
- sql_calls: `5`
- api_calls: `3`
- compiled_sql_count: `5`
- compiled_api_count: `3`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_initial_failures: `0`
- final_semantic_gate_final_failures: `0`
- final_unavailable_with_runtime_facts: `0`
- ready_to_run_dev_eval: `true`

## Smoke Rows

| Prompt ID | Pass | SQL | API | Runtime Facts | Final Gate Failures | Final Answer Repair Attempts |
|---|---:|---:|---:|---:|---:|---:|
| pure_concept_schema | true | 0 | 0 | 0 | 0 | 0 |
| pure_meta_list_schemas | true | 0 | 0 | 0 | 0 | 0 |
| ambiguous_user_schemas | true | 1 | 0 | 3 | 0 | 0 |
| local_schema_count | true | 1 | 0 | 1 | 0 | 0 |
| birthday_message_published | true | 1 | 1 | 1 | 0 | 0 |
| mixed_inactive_journeys | true | 1 | 1 | 2 | 0 | 0 |
| compare_local_live_birthday_status | true | 1 | 1 | 1 | 0 | 0 |

## Objective Notes

- The final composer now receives explicit available fact and failed-source sections.
- API/live failures no longer mask successful local evidence.
- The count smoke now executes a real `COUNT(*)` query and answers `74`.
- The schema inventory smoke now answers with count plus sample names and passes semantic grounding.
- No unsupported claims were introduced.
- Dev eval was not run; the request said not to run it unless the smoke target was reached.
