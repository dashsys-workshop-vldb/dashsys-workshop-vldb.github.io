# Local Qwen V2 Schema Binding Stabilization

## Objective

Stabilize V2 after the schema-binding experiment regressed focused smoke. Schema binding remains available as experimental code, but it is no longer a default live planner stage.

## Code Changes

Runtime:

- `dashagent/v2_semantic_ir_planner.py`
  - Added `V2_ENABLE_SCHEMA_BINDING` env gate.
  - Default behavior is schema binding disabled with repair-card hints only.
  - `V2_ENABLE_SCHEMA_BINDING=1` enables the experimental `submit_schema_binding_plan` toolcall path.
  - Added trace fields:
    - `schema_binding_enabled`
    - `schema_binding_mode`
    - existing `schema_binding_used` / validation fields remain.
  - Strengthened LLM-owned routing instructions:
    - `"What schemas do I have?"` is actual-record evidence, not pure concept.
    - local schema counts are `COUNT` over `LOCAL_SNAPSHOT`.
  - Added compact repair prompt context:
    - `allowed_fields_for_error_table`
    - `field_role_cards`
    - `relationship_cards`
    - explicit instruction to choose exact table/field IDs from allowed cards.

Smoke/report diagnostics:

- `scripts/run_hermes_v2_toolcall_smoke.py`
  - Exposes `schema_binding_enabled` and `schema_binding_mode` per row.
  - Adds summary counts for schema-binding enabled rows and modes.

Tests:

- `tests/test_v2_semantic_ir.py`
  - Default path does not call `submit_schema_binding_plan`.
  - `V2_ENABLE_SCHEMA_BINDING=1` enables the experimental binding toolcall.
  - Answer Contract remains active while schema binding is disabled.
  - Repair prompts include table/field/relationship cards.
  - Backend still does not rewrite `LocalQueryIR`.

- `tests/test_hermes_v2_toolcall_smoke.py`
  - Smoke row/summary diagnostics include schema-binding enabled/mode fields.

## Schema Binding Default

| Setting | Value |
| --- | --- |
| Default env | `V2_ENABLE_SCHEMA_BINDING=0` / unset |
| Default toolcall stage | disabled |
| Default row mode | `repair_hint_only` |
| Experimental enable | `V2_ENABLE_SCHEMA_BINDING=1` |
| Backend semantic table/field selection | no |
| Packaged default strategy | `SQL_FIRST_API_VERIFY` unchanged |

## Validation

Commands run:

```bash
.venv/bin/python -m pytest -q tests/test_v2_semantic_ir.py
.venv/bin/python -m pytest -q tests/test_v2_semantic_ir.py tests/test_hermes_v2_toolcall_smoke.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_submission_ready.py
.venv/bin/python scripts/generate_sdk_usage_audit.py
git diff --check
```

Results:

| Check | Result |
| --- | --- |
| `tests/test_v2_semantic_ir.py` | `42 passed` |
| focused affected tests | `55 passed` |
| full pytest | `1223 passed, 1 skipped` |
| `check_submission_ready.py` | `ok=true` |
| packaged default | `SQL_FIRST_API_VERIFY` |
| query output count | `73` |
| secret scan | no hits |
| SDK usage audit | `runtime_llm_direct_http_hits=0` |
| `git diff --check` | passed |

## Local Qwen Probe

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
V2_ENABLE_SCHEMA_BINDING=0 \
.venv/bin/python scripts/probe_hermes_sdk_toolcall.py
```

Result:

- `ok=true`
- provider: `openai`
- SDK path used: `true`
- toolcall supported: `true`
- tool calls: `1`
- tool name: `submit_probe_result`

## Focused Smoke Result

Command:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit \
OPENAI_API_KEY=local-token \
LLM_TIMEOUT_SECONDS=180 \
HERMES_LLM_CALL_TIMEOUT_SEC=180 \
V2_ENABLE_SCHEMA_BINDING=0 \
.venv/bin/python scripts/run_hermes_v2_toolcall_smoke.py
```

Result: failed, so strict dev eval was not run.

| Metric | Before Stabilization | After Stabilization |
| --- | ---: | ---: |
| row_count | 7 | 7 |
| passed_count | 2 | 2 |
| failed_count | 5 | 5 |
| timeout_count | 2 | 0 |
| unsupported_claims | 0 | 0 |
| no_tool_fp | 3 | 2 |
| final_semantic_gate_final_failures | 0 | 2 |
| missing_answer_contract_count | 0 | 0 |
| unknown_table_count | 0 | 0 |
| unknown_field rows | 1+ | 3 |
| schema_binding_enabled_count | not reported | 0 |
| schema_binding_used_count | 1 | 0 |
| schema_binding_mode | experimental on one row | `repair_hint_only` on all rows |

Current smoke summary:

| Metric | Value |
| --- | ---: |
| row_count | 7 |
| passed_count | 2 |
| failed_count | 5 |
| timeout_count | 0 |
| unsupported_claims | 0 |
| no_tool_fp | 2 |
| final_semantic_gate_initial_failures | 2 |
| final_semantic_gate_final_failures | 2 |
| missing_answer_contract_count | 0 |
| unknown_table_count | 0 |
| runtime_fact_count | 1 |
| local_snapshot_fact_count | 1 |
| live_api_fact_count | 0 |
| sql_calls | 2 |
| api_calls | 2 |
| compiled_sql_count | 2 |
| compiled_api_count | 2 |
| raw_sql_fallback_used_count | 0 |
| schema_binding_enabled_count | 0 |
| schema_binding_used_count | 0 |

## Smoke Rows

| Prompt ID | Pass | Route | SQL | API | No-tool FP | Binding Enabled | Binding Used | Mode | Validation | Final Gate Final Failures | Observation |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- |
| `pure_concept_schema` | true | `LLM_DIRECT` | 0 | 0 | false | false | false | `repair_hint_only` | passed | 0 | Correct direct concept path. |
| `pure_meta_list_schemas` | true | `LLM_DIRECT` | 0 | 0 | false | false | false | `repair_hint_only` | passed | 0 | Correct direct meta path. |
| `ambiguous_user_schemas` | false | `EVIDENCE_PIPELINE` | 0 | 1 | false | false | false | `repair_hint_only` | passed | 1 | Routing improved from direct to evidence, but chose live API and produced unavailable answer. |
| `local_schema_count` | false | `EVIDENCE_PIPELINE` | 1 | 0 | false | false | false | `repair_hint_only` | passed | 0 | Still selects wrong schema-valid table and answers `0` instead of expected `74`. |
| `birthday_message_published` | false | `EVIDENCE_PIPELINE` | 0 | 0 | true | false | false | `repair_hint_only` | `unknown_field` | 0 | Unknown-field repair still fails before evidence execution. |
| `mixed_inactive_journeys` | false | `EVIDENCE_PIPELINE` | 0 | 0 | true | false | false | `repair_hint_only` | `unknown_field` | 0 | Unknown-field repair still fails before evidence execution. |
| `compare_local_live_birthday_status` | false | `EVIDENCE_PIPELINE` | 1 | 1 | false | false | false | `repair_hint_only` | initial `unknown_field`, final valid enough to execute | 1 | Executes local/live paths, but final gate still rejects final answer. |

## Strict Dev Eval

Not run. The focused smoke did not meet the required gate:

- required `passed_count=7`, actual `2`
- required `timeout_count=0`, actual `0`
- required `unsupported_claims=0`, actual `0`
- required `no_tool_fp=0`, actual `2`
- required `final_semantic_gate_final_failures=0`, actual `2`
- required `schema_binding_enabled=false` by default, actual `false` on all rows
- required `schema_binding_used=false` by default, actual `false` on all rows

## Remaining Blockers

1. Local schema-source selection is still weak. `What schemas do I have?` now enters evidence, but chooses live API instead of local snapshot.
2. Local schema-count table selection remains wrong. Backend correctly does not override the LLM's schema-valid but semantically wrong table choice.
3. Unknown-field repair still fails for date and mixed prompts.
4. Final answer semantic gate still rejects two evidence/caveat answers.

## Recommendation

- Safe to keep this stabilization patch: yes.
- Safe to commit: yes, as a stabilization/diagnostic patch, because it removes the default schema-binding toolcall regression and preserves packaged default safety.
- Safe to run strict V2 dev eval: no.
- Safe to promote V2: no.

Next work should remain LLM-owned and target:

- better compact schema cards/table role wording for local schema/blueprint tables;
- better unknown-field repair context for date/status/name fields;
- evidence-source preference repair when prompt is local/user-specific and the model chooses live API without live cues;
- final semantic gate behavior for scoped caveat answers.

