# Answer Contract Stability Fix Report

## Summary

The V2 Answer Contract stability fix was implemented and validated locally with the OpenAI-compatible Qwen3.6 SDK-toolcall backend. The targeted contract-stability failures are fixed:

- Missing answer contract after Semantic IR repair: `0`
- Unknown table failures after Semantic IR repair: `0`
- Unsupported claims: `0`
- No-tool false positives: `0`
- Final semantic gate final failures: `0`
- Smoke timeouts: `0`

Fresh smoke completed all 7 focused rows, but only 3/7 passed. Per the requested stop condition, strict dev eval was not run.

## Files Changed

Runtime changes:

- `dashagent/v2_answer_contract.py`
- `dashagent/v2_answer_contract_planner.py`
- `dashagent/v2_semantic_ir_planner.py`
- `dashagent/v2_semantic_ir_validator.py`
- `scripts/run_hermes_v2_toolcall_smoke.py`

Tests updated:

- `tests/test_v2_answer_contract.py`
- `tests/test_v2_semantic_ir.py`
- `tests/test_hermes_v2_toolcall_smoke.py`

Smoke output artifacts were refreshed under:

- `outputs/hermes_toolcall_*`
- `outputs/reports/hermes_v2_toolcall_smoke/`

## Implementation Details

Added a contract-only SDK toolcall planner:

- Tool name: `submit_answer_contract`
- Module: `dashagent/v2_answer_contract_planner.py`
- Purpose: ask the LLM to supply only the missing/invalid `answer_contract` for an already-owned Semantic IR plan.
- Constraint: it does not change tasks, tables, endpoints, fields, filters, or aggregation semantics.

Relaxed primary Semantic IR parsing only as an intermediate state:

- Initial EVIDENCE plans may parse without `answer_contract`.
- Before execution, V2 calls the contract-only planner if the contract is missing or invalid.
- Final EVIDENCE plan still requires a valid `answer_contract`.
- If the secondary contract call fails, the plan fails closed.

Added compact answer contract normalization:

- `answer_style` mechanically defaults from slot type.
- `must_not_assert_positive_if_zero_rows` mechanically defaults for relation/list/lookup/status slots.
- `source_scope` remains required per slot; no backend source inference was added.

Improved validation/repair diagnostics:

- Semantic IR validation now records `bad_table`, `bad_field`, `bad_endpoint`, and table role cards.
- Repair prompts include allowed table choices and table role cards.
- Backend still does not choose replacement tables, fields, endpoints, filters, or SQL/API paths.

Improved smoke runner robustness:

- One row exception is recorded as a row failure instead of aborting the whole smoke.
- Summary now includes `missing_answer_contract_count` and `unknown_table_count`.
- Rows expose answer-contract and Semantic IR validation error diagnostics.

## Local Qwen Probe

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
.venv/bin/python scripts/probe_hermes_sdk_toolcall.py
```

Result:

- `ok=true`
- `provider=openai`
- `sdk_path_used=true`
- `toolcall_supported=true`
- `tool_calls_count=1`
- `tool_name=submit_probe_result`

## Fresh Smoke Result

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
HERMES_SMOKE_PROMPT_TIMEOUT_SEC=180 \
.venv/bin/python scripts/run_hermes_v2_toolcall_smoke.py
```

Top-level result:

- `ok=false`
- `row_count=7`
- `passed_count=3`
- `failed_count=4`
- `timeout_count=0`
- `unsupported_claims=0`
- `no_tool_fp=0`
- `final_semantic_gate_final_failures=0`
- `missing_answer_contract_count=0`
- `unknown_table_count=0`
- `sql_calls=5`
- `api_calls=1`
- `compiled_sql_count=5`
- `compiled_api_count=0`
- `runtime_fact_count=4`
- `local_snapshot_fact_count=4`
- `live_api_fact_count=0`
- `raw_sql_fallback_used_count=0`

## Smoke Row Table

| Prompt ID | Pass | Route | SQL | API | Runtime Facts | Final Answer Summary | Failure Notes |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `pure_concept_schema` | yes | `LLM_DIRECT` | 0 | 0 | 0 | Concept definition of schema | None |
| `pure_meta_list_schemas` | yes | `LLM_DIRECT` | 0 | 0 | 0 | Explains the word "list" generally | None |
| `ambiguous_user_schemas` | no | `EVIDENCE_PIPELINE` | 1 | 0 | 0 | No matching runtime evidence | LLM selected `hkg_br_base_segment_used_by_dependent_segment` and `SEGMENTID`; query returned zero rows |
| `local_schema_count` | no | `EVIDENCE_PIPELINE` | 1 | 0 | 1 | `0 schema records` | LLM counted the segment-dependency table, producing `0`; smoke expected answer containing `74` |
| `birthday_message_published` | no | `EVIDENCE_PIPELINE` | 1 | 0 | 0 | No matching runtime evidence | Repair fixed validation, but final local lookup used `dim_blueprint.UPDATEDCLIENTID = "Birthday Message"` and returned zero rows |
| `mixed_inactive_journeys` | yes | `EVIDENCE_PIPELINE` | 1 | 0 | 3 | Concept caveat plus local inactive journey evidence | Passed smoke, though concept slot reported runtime error |
| `compare_local_live_birthday_status` | no | `EVIDENCE_PIPELINE` | 1 | 1 | 0 | Local zero rows plus live API unavailable caveat | Semantic IR repair failed on unknown field `NAME` for `dim_blueprint`; live API was dry-run unavailable |

## Remaining Blockers

The contract integration no longer appears to be the blocker. The remaining failures are evidence-content failures from LLM-owned source/field choices:

1. `What schemas do I have?` used a local segment-dependency table and returned zero rows.
2. `How many schema records are in the local snapshot?` compiled and executed, but counted the wrong local table and returned `0` instead of the smoke expectation containing `74`.
3. `When was the journey "Birthday Message" published?` repaired an initial unknown-field issue, but the final local lookup returned zero rows.
4. `Compare local and live status of Birthday Message if both are available.` still failed Semantic IR validation after one repair because the LLM used an unknown field; the fallback answer stayed scoped and did not make unsupported claims.

These are not safe to fix by backend semantic routing under the current architecture constraints. A next pass should improve LLM-facing schema cards, table role descriptions, and field examples while preserving LLM ownership of table/field selection.

## Validation

Focused red/green tests:

```bash
.venv/bin/python -m pytest -q \
tests/test_v2_answer_contract.py::test_compact_count_slot_normalizes_mechanical_defaults \
tests/test_v2_answer_contract.py::test_compact_list_and_relation_slots_normalize_positive_assertion_guard \
tests/test_v2_answer_contract.py::test_compact_slot_still_requires_task_reference_and_source_scope \
tests/test_v2_semantic_ir.py::test_missing_answer_contract_uses_secondary_contract_toolcall \
tests/test_v2_semantic_ir.py::test_invalid_secondary_answer_contract_fails_closed_without_atomic_fallback \
tests/test_v2_semantic_ir.py::test_direct_route_does_not_require_secondary_answer_contract \
tests/test_v2_semantic_ir.py::test_semantic_ir_validator_checks_existence_without_correction \
tests/test_v2_semantic_ir.py::test_llm_unified_planner_repairs_invalid_semantic_ir_once \
tests/test_hermes_v2_toolcall_smoke.py::test_smoke_records_row_failure_and_continues_all_prompts
```

Result: `9 passed in 0.96s`

Focused module tests:

```bash
.venv/bin/python -m pytest -q \
tests/test_v2_answer_contract.py \
tests/test_final_answer_contract_gate.py \
tests/test_v2_semantic_ir.py \
tests/test_v2_semantic_ir_support.py \
tests/test_hermes_v2_toolcall_smoke.py \
tests/test_robust_generalized_candidate.py \
tests/test_llm_owned_v2_workflow.py \
tests/test_llm_final_answer_composer.py
```

Result: `160 passed in 9.91s`

Full validation:

```bash
.venv/bin/python -m pytest -q
```

Result: `1213 passed, 1 skipped in 94.34s`

```bash
.venv/bin/python scripts/check_submission_ready.py
```

Result: `ok=true`; packaged default remains `SQL_FIRST_API_VERIFY`; query output count `73`; secret scan `ok=true`.

```bash
.venv/bin/python scripts/generate_sdk_usage_audit.py
```

Result: `runtime_llm_direct_http_hits=0`

```bash
git diff --check
```

Result: passed with no output.

## Dev Eval Status

Strict dev eval was not run. The continuation gate required:

- `passed_count=7`
- `unsupported_claims=0`
- `no_tool_fp=0`
- `final_semantic_gate_final_failures=0`

The fresh smoke had `passed_count=3`, so the correct action was to stop and report blockers.

## Recommendation

Safe to keep as a shadow-only contract stability fix. It is not safe to benchmark or promote V2 yet because focused smoke still fails 4/7. Packaged default remains unchanged as `SQL_FIRST_API_VERIFY`.
