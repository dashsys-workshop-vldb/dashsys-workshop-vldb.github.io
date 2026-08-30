# Final Two Rows Grounding Fix

## Objective

Fix the remaining focused Hermes/Qwen3.6 V2 SDK-toolcall Semantic IR smoke failures for:

- `birthday_message_published`
- `mixed_inactive_journeys`

The packaged default remains `SQL_FIRST_API_VERIFY`. V2 remains shadow/research-only and is not promoted.

## Root Causes

| Prompt ID | Failure Class | Evidence | Fix |
|---|---|---|---|
| `birthday_message_published` | Mechanical dependency placeholder issue | The LLM plan produced `{{t1_lookup_journey_id.CAMPAIGNID}}`; the backend resolver only accepted `{{pass.result.field}}`, so the date pass was dependency-blocked even though the first SQL pass had `CAMPAIGNID`. | Accept shorthand `{{pass_id.field}}` as a mechanical alias for `{{pass_id.result.field}}`; add case-insensitive field lookup against completed pass rows. |
| `mixed_inactive_journeys` | Final semantic gate false positives and oversized final-answer card | The semantic gate treated conceptual words such as `active` and the product phrase `Journey Optimizer` as unsupported hard runtime claims. Repair then removed useful grounded content. | Allow active/inactive when used in conceptual contrast, treat product-context phrases as generic, compact result-bundle/pass previews, and bound the final-answer token budget. |

## Files Changed

- `dashagent/executor.py`
- `dashagent/final_answer_claim_extractor.py`
- `dashagent/llm_final_answer_composer.py`
- `tests/test_llm_owned_v2_workflow.py`
- `tests/test_llm_final_answer_composer.py`
- `tests/test_v2_structured_tool_output.py`
- Generated smoke/eval/gate reports under `outputs/`

## Implementation Details

- Placeholder resolution now supports both `{{pass_id.result.FIELD}}` and `{{pass_id.FIELD}}`.
- Placeholder resolution still reads only completed runtime pass results; it does not infer tables, columns, filters, endpoints, or user intent.
- Final-answer claim extraction no longer treats conceptual `active` / `inactive` contrast as unsupported status claims.
- `Journey Optimizer` and `Adobe Experience Platform` are treated as product-context phrases, not runtime entity claims.
- The final-answer composer now sends a compact `ResultBundle` preview and keeps final-answer generation bounded at 260 tokens.
- The final-answer prompt now explicitly requests concise evidence-grounded answers.

## Latest Focused Smoke

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai OPENAI_BASE_URL=http://localhost:8000/v1 OPENAI_MODEL=<local-qwen3.6-model> HERMES_SMOKE_PROMPT_TIMEOUT_SEC=120 HERMES_LLM_CALL_TIMEOUT_SEC=60 python3 scripts/run_hermes_v2_toolcall_smoke.py
```

Result:

- `row_count`: 7
- `passed_count`: 7
- `failed_count`: 0
- `timeout_count`: 0
- `unsupported_claims`: 0
- `no_tool_fp`: 0
- `final_semantic_gate_initial_failures`: 0
- `final_semantic_gate_final_failures`: 0
- `raw_sql_fallback_used_count`: 0
- `runtime_fact_count`: 9
- `local_snapshot_fact_count`: 9
- `live_api_fact_count`: 0
- `sql_calls`: 6
- `api_calls`: 2

## Smoke Rows

| Prompt ID | Pass | SQL | API | Runtime Facts | Final Gate Initial Failures | Final Gate Final Failures | Final Answer |
|---|---:|---:|---:|---:|---:|---:|---|
| `pure_concept_schema` | true | 0 | 0 | 0 | 0 | 0 | A schema is a definition or blueprint that describes the structure, format, and rules for data. |
| `pure_meta_list_schemas` | true | 0 | 0 | 0 | 0 | 0 | Explains that `list` means display/enumerate schema records. |
| `ambiguous_user_schemas` | true | 1 | 0 | 3 | 0 | 0 | Local snapshot count plus example schemas. |
| `local_schema_count` | true | 1 | 0 | 1 | 0 | 0 | There are 74 schema records in the local snapshot. |
| `birthday_message_published` | true | 2 | 0 | 2 | 0 | 0 | The journey `Birthday Message` was published on `2026-03-31T06:07:32.838462639Z`. |
| `mixed_inactive_journeys` | true | 1 | 1 | 2 | 0 | 0 | Concept sentence plus two local journeys and scoped live API caveat. |
| `compare_local_live_birthday_status` | true | 1 | 1 | 1 | 0 | 0 | Local status plus scoped live API caveat. |

## Validation

| Command | Result |
|---|---|
| `python3 -m pytest -q tests/test_v2_structured_tool_output.py tests/test_llm_final_answer_composer.py tests/test_llm_owned_v2_workflow.py tests/test_hermes_v2_toolcall_smoke.py` | `74 passed` |
| `python3 -m pytest -q` | `1138 passed, 1 skipped` |
| `python3 scripts/check_submission_ready.py` | `ok: true`; default remains `SQL_FIRST_API_VERIFY`; query output count `73`; secret scan `ok: true` |
| `python3 scripts/generate_sdk_usage_audit.py` | `runtime_llm_direct_http_hits: 0` |
| `git diff --check` | passed |

## Gate Results

- `python3 scripts/run_semantic_route_promotion_gate.py`: `promotion_allowed=false`, recommendation `keep_shadow_only`.
- `python3 scripts/run_integrated_robustness_gate.py`: passed; recommendation `promote_efficiency_recovery_fix` for a separate packaged-efficiency gate, not V2 promotion.
- `python3 scripts/run_hidden_style_eval.py`: 48/48 cases passed.

## Decision

- Safe to keep: yes.
- Safe to commit: yes, based on full pytest, readiness, SDK audit, and diff check.
- Safe to benchmark: focused smoke is ready; full V2 strict dev eval still needs hang diagnostics before treating benchmark output as reliable.
- Safe to promote V2: no. V2 strict dev eval did not complete, and the semantic route promotion gate says `keep_shadow_only`.
