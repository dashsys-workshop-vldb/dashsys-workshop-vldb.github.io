# Local Qwen V2 Schema Binding Fix Report

## Objective

Add an LLM-owned Schema/Table/Field Binding layer for the V2 Semantic IR planner, then run local Qwen3.6 focused smoke before any strict dev eval.

## Files Changed

Runtime:

- `dashagent/v2_schema_binding.py`
- `dashagent/v2_schema_binding_validator.py`
- `dashagent/v2_schema_binding_planner.py`
- `dashagent/v2_semantic_ir.py`
- `dashagent/v2_semantic_ir_validator.py`
- `dashagent/v2_semantic_ir_planner.py`
- `dashagent/v2_semantic_ir_compiler.py`
- `dashagent/v2_semantic_ir_context.py`
- `scripts/run_hermes_v2_toolcall_smoke.py`

Tests:

- `tests/test_v2_schema_binding.py`
- `tests/test_v2_semantic_ir.py`
- `tests/test_hermes_v2_toolcall_smoke.py`

Reports and smoke artifacts under `outputs/` were updated by smoke, readiness, SDK audit, and report generation.

## Implementation Summary

- Added `SchemaBinding` and `SchemaBindingPlan` as a separate LLM-owned binding contract.
- Added `submit_schema_binding_plan` SDK tool schema and binding planner.
- Added `SchemaBindingValidator` to check only mechanical validity:
  - unique binding IDs
  - known tables
  - known fields
  - known relation tables
  - valid answer-slot references
  - task/local-query binding references
  - local-query table consistency with a referenced binding
- Extended Semantic IR with `binding_id` at task and local query level.
- Attached schema-binding diagnostics to the V2 planner trace.
- Enhanced context cards with mechanical object/table/field role hints.
- Added smoke diagnostics for schema-binding counts, IDs, validation result, repair attempts, and repair success.
- Added optional smoke worker start method via `HERMES_SMOKE_MP_START_METHOD`; `spawn` was needed with the bundled Python runtime to avoid worker exit code `-11`.

The backend still does not choose semantic intent, table, endpoint, fields, filters, or answers. The binding layer validates LLM-owned bindings but does not replace or repair semantically wrong but schema-valid choices.

## Local Runtime Notes

The repo `.venv` Python interpreter became unusable in this session before imports. The working validation runtime was:

```bash
PYTHONPATH=.venv/lib/python3.12/site-packages /Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

This workaround successfully imported repo dependencies and ran tests/scripts.

## Local Qwen Probe

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
PYTHONPATH=.venv/lib/python3.12/site-packages \
/Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/probe_hermes_sdk_toolcall.py
```

Result:

- `ok=true`
- provider: `openai`
- SDK path used: `true`
- toolcall supported: `true`
- tool call count: `1`
- tool name: `submit_probe_result`

## Fresh Focused Smoke

Command:

```bash
HERMES_SMOKE_MP_START_METHOD=spawn \
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
HERMES_SMOKE_PROMPT_TIMEOUT_SEC=180 \
PYTHONPATH=.venv/lib/python3.12/site-packages \
/Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/run_hermes_v2_toolcall_smoke.py
```

Result: focused smoke completed but failed the gate.

| Metric | Value |
| --- | ---: |
| row_count | 7 |
| passed_count | 2 |
| failed_count | 5 |
| timeout_count | 2 |
| unsupported_claims | 0 |
| no_tool_fp | 3 |
| final_semantic_gate_initial_failures | 1 |
| final_semantic_gate_final_failures | 0 |
| runtime_fact_count | 1 |
| local_snapshot_fact_count | 1 |
| live_api_fact_count | 0 |
| sql_calls | 2 |
| api_calls | 1 |
| compiled_sql_count | 1 |
| compiled_api_count | 0 |
| raw_sql_fallback_used_count | 0 |
| atomic_protocol_fallback_count | 0 |
| schema_binding_used_count | 1 |
| schema_binding_validation_failure_count | 0 |
| schema_binding_repair_attempt_count | 0 |
| schema_binding_repair_success_count | 0 |

## Smoke Rows

| Prompt ID | Pass | Timeout | Route | SQL | API | No-tool FP | Binding | Runtime facts | Final gate final failures | Main observation |
| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: | --- |
| pure_concept_schema | true | false | LLM_DIRECT | 0 | 0 | false | false | 0 | 0 | Correct direct concept answer. |
| pure_meta_list_schemas | true | false | LLM_DIRECT | 0 | 0 | false | false | 0 | 0 | Correct direct meta-language answer. |
| ambiguous_user_schemas | false | false | LLM_DIRECT | 0 | 0 | true | false | 0 | 0 | Data-like prompt incorrectly bypassed evidence, so binding never ran. |
| local_schema_count | false | false | EVIDENCE_PIPELINE | 1 | 0 | false | true | 1 | 0 | Binding validated, but the LLM bound to a schema-valid wrong table and answered 0. |
| birthday_message_published | false | true | null | 0 | 0 | true | false | 0 | 0 | Timed out at `checkpoint_llm_owned_pass_graph_gate`. |
| mixed_inactive_journeys | false | true | null | 0 | 0 | true | false | 0 | 0 | Timed out at `checkpoint_llm_unified_planner_start`. |
| compare_local_live_birthday_status | false | false | EVIDENCE_PIPELINE | 1 | 1 | false | false | 0 | 0 | Semantic IR remained invalid with `unknown_field`; binding did not run. |

## Before / After Context

The latest known pre-binding smoke state in this working context was not rerun in this pass. It was recorded as failing, with focused smoke not ready for strict dev eval. After this binding change, fresh smoke is still failing: `2/7` passed with `unsupported_claims=0`, `no_tool_fp=3`, and `timeout_count=2`.

## Blockers

1. `What schemas do I have?` still goes `LLM_DIRECT`, producing a no-tool false positive. The binding layer cannot help if the pre-binding plan chooses direct routing.
2. `How many schema records are in the local snapshot?` now runs binding, but the LLM selected a schema-valid wrong table. The backend correctly did not semantically override it.
3. `When was the journey "Birthday Message" published?` timed out at `checkpoint_llm_owned_pass_graph_gate`.
4. `Explain what inactive journey means and show inactive journeys.` timed out at `checkpoint_llm_unified_planner_start`.
5. `compare_local_live_birthday_status` still has an `unknown_field` Semantic IR validation failure before binding can repair the table/field association.

## Strict Dev Eval

Strict dev eval was not run because the focused smoke did not satisfy the required gate:

- required `passed_count=7`
- required `unsupported_claims=0`
- required `no_tool_fp=0`
- required `final_semantic_gate_final_failures=0`

Actual smoke had `passed_count=2`, `no_tool_fp=3`, and `timeout_count=2`.

## Validation

Commands run with the bundled Python workaround:

```bash
PYTHONPATH=.venv/lib/python3.12/site-packages /Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
PYTHONPATH=.venv/lib/python3.12/site-packages /Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_submission_ready.py
PYTHONPATH=.venv/lib/python3.12/site-packages /Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_sdk_usage_audit.py
git diff --check
```

Results:

- pytest: `1220 passed, 1 skipped`
- `check_submission_ready.py`: `ok=true`
- packaged default: `SQL_FIRST_API_VERIFY`
- query output count: `73`
- secret scan: no hits
- SDK usage audit: `runtime_llm_direct_http_hits=0`
- `git diff --check`: passed

## Recommendation

- Safe to keep as shadow-only diagnostic infrastructure: yes.
- Safe to benchmark V2 now: no.
- Safe to promote V2: no.
- Safe to commit as a readiness fix: no; smoke is worse than the required gate.
- Potentially safe to commit only if explicitly labeled as experimental binding infrastructure with known smoke blockers.

Next useful work should target the remaining planner failures without backend semantic takeover:

- force evidence routing for data-like "my/local snapshot" schema prompts through the LLM-owned planner contract;
- improve LLM-owned binding prompt/card quality so the model binds schema-count prompts to actual schema/blueprint tables;
- make binding available in repair paths for unknown-field Semantic IR failures;
- reduce or bound local Qwen planner-stage latency for pass-graph and unified-planner starts.

