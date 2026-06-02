# Final Blocker Fix Summary

- generated_at_utc: `2026-06-02T14:49:54Z`
- packaged default unchanged: `SQL_FIRST_API_VERIFY`
- V2 promotion: not attempted
- Pioneer/Gemini: not used
- strict dev eval: not run because fresh smoke failed

## Files Changed

Source/test files changed in this pass:

- `dashagent/executor.py`
- `dashagent/llm_final_answer_composer.py`
- `dashagent/v2_semantic_ir_planner.py`
- `tests/test_v2_pipeline_scheduler.py`
- `tests/test_llm_final_answer_composer.py`
- `tests/test_v2_semantic_ir.py`

Normal smoke/report outputs were also updated under `outputs/`.

## Implementation Summary

1. Dependency resolution hardening:
   - Added `_dependency_precheck`.
   - Placeholder-dependent consumers now fail closed before LLM repair if a required dependency is missing or terminal-failed.
   - Dependency failure PassResults now use terminal status `DEPENDENCY_FAILED`.
   - Order-only failed dependencies do not block later SQL/API passes when the consumer does not reference dependency output.

2. Relationship evidence exposure:
   - Added runtime ID-to-name indexing across successful pass rows.
   - Added relation facts for true ID bridge rows and class/schema/blueprint/type-to-ID rows.
   - This supports audience-to-destination and schema-class-to-policy evidence already selected by the LLM.

3. Requested-status grounding:
   - Added a semantic gate check that blocks answers listing row IDs/names when row status conflicts with an explicitly requested status.
   - Kept inactive prompts permissive for non-active lifecycle values such as `created` and `updated`; explicit active-like rows remain blocked.

4. Semantic IR planner guidance:
   - Added one generic LLM-owned prompt rule telling the planner to include relationship-bearing fields for mapping/default/schema-class/merge-policy prompts when such fields exist in the selected allowed table.
   - Backend still does not choose tables, endpoints, fields, filters, or semantic intent.

## Test Results

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_v2_pipeline_scheduler.py tests/test_llm_final_answer_composer.py tests/test_v2_semantic_ir.py` | `79 passed` |
| `DASHAGENT_LLM_PROVIDER=openai ... .venv/bin/python scripts/probe_hermes_sdk_toolcall.py` | `ok=true`; SDK path used; toolcall supported |
| `DASHAGENT_LLM_PROVIDER=openai ... .venv/bin/python scripts/run_hermes_v2_toolcall_smoke.py` | `ok=false`; `6/7` rows passed; one timeout |
| `.venv/bin/python -m pytest -q` | `1188 passed, 1 skipped` |
| `.venv/bin/python scripts/check_submission_ready.py` | `ok=true` |
| `.venv/bin/python scripts/generate_sdk_usage_audit.py` | `runtime_llm_direct_http_hits=0` |
| `git diff --check` | passed |

## Smoke Row Status

| Prompt | Pass | Timeout | SQL | API | Runtime facts | Notes |
|---|---|---:|---:|---:|---:|---|
| `pure_concept_schema` | true | false | 0 | 0 | 0 | direct route bypass preserved |
| `pure_meta_list_schemas` | true | false | 0 | 0 | 0 | direct route bypass preserved |
| `ambiguous_user_schemas` | true | false | 1 | 0 | 3 | evidence path used |
| `local_schema_count` | true | false | 1 | 0 | 1 | local count path used |
| `birthday_message_published` | true | false | 1 | 0 | 1 | local date path used |
| `mixed_inactive_journeys` | true | false | 1 | 0 | 2 | fixed after dependency/status changes |
| `compare_local_live_birthday_status` | false | true | 0 | 0 | 0 | timed out at `checkpoint_llm_unified_planner_start` |

## Remaining Blocker

The remaining blocker is local Qwen planner latency/timeout on `compare_local_live_birthday_status`. The row timed out before producing a plan, so no SQL/API evidence was acquired. This prevents running strict V2 dev eval under the requested gate.

## Safety Result

- Unsupported claims: `0`
- Final semantic gate final failures: `0`
- Raw SQL fallback used count: `0`
- SDK direct HTTP hits: `0`
- Packaged default: unchanged
- No V2 promotion performed

## Recommendation

Safe to keep the narrow code changes. Not safe to promote. Not safe to run strict dev eval as benchmark evidence until the remaining local Qwen planner timeout is resolved or the smoke gate is adjusted by explicit instruction.
