# Gemini Smoke Failure Fix

Classification: `keep_trial_only`

This pass made narrow V2 smoke fixes only. It did not change the packaged default, did not promote V2, did not use Pioneer, did not add backend semantic routing, and did not run dev eval or benchmark.

## Files Changed

- `dashagent/executor.py`
- `dashagent/llm_final_answer_composer.py`
- `dashagent/v2_semantic_ir_planner.py`
- `scripts/run_hermes_v2_toolcall_smoke.py`
- `tests/test_hermes_v2_toolcall_smoke.py`
- `tests/test_llm_final_answer_composer.py`
- `tests/test_v2_semantic_ir.py`

## Root Causes And Fixes

| Row | Root cause | Narrow fix |
| --- | --- | --- |
| `ambiguous_user_schemas` | The Gemini trajectory compacted the successful SQL result into a truncated preview, so the smoke metric did not count local facts even though SQL succeeded and the final answer was grounded. | Count compacted successful local SQL evidence from `checkpoint_result_bundle` plus `checkpoint_llm_final_answer_composer.slot_counts` for smoke metrics only. |
| `mixed_inactive_journeys` | The LLM-owned Semantic IR chose `CONCEPT + LIVE_QUERY` for a mixed concept-and-record prompt with no live/current/platform/API cue. | Strengthened Semantic IR prompt instructions with a general show/list-records local rule, an inactive-journey local snapshot rule, and an explicit `CONCEPT + LOCAL_QUERY` example. |
| `compare_local_live_birthday_status` | The safe fallback used generic could-not-compose wording when local facts existed, and executor diagnostics still recorded the failed pre-fallback semantic gate. | Fallback now returns scoped evidence-state wording and the executor semantically rechecks the fallback before recording final answer diagnostics. |

## Smoke Before

Source: user-provided current objective state and the pre-fix Gemini smoke report.

- passed_count: `4`
- failed_count: `3`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- compiled_sql_count: `4`
- compiled_api_count: `2`
- final_semantic_gate_final_failures: `1`

## Smoke After Attempt

Command shape used:

```bash
DASHAGENT_LLM_PROVIDER=openai \
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ \
OPENAI_API_KEY=$GEMINI_API_KEY \
OPENAI_MODEL=gemini-3.5-flash \
python3 scripts/run_hermes_v2_toolcall_smoke.py
```

Result in this Codex process:

- ok: `false`
- skipped: `true`
- skip_reason: `Gemini OpenAI-Compatible V2 Toolcall Smoke probe did not return native SDK tool/function calls.`
- probe_error: `<html><title>Error 400 (Bad Request)!!1</title></html>`
- row_count: `0`
- passed_count: `0`
- failed_count: `0`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_final_failures: `0`

The locally visible `GEMINI_API_KEY` still returns HTML 400 for both raw REST and SDK OpenAI-compatible probe calls. The payload key difference remains empty: raw REST and SDK both use `model`, `messages`, `tools`, and `tool_choice` in the same order.

## Validation

- Focused red-to-green regressions: `4 passed`
- Related tests: `60 passed`
- Full pytest: `1161 passed, 1 skipped`
- `python3 scripts/check_submission_ready.py`: passed, default remains `SQL_FIRST_API_VERIFY`
- `python3 scripts/generate_sdk_usage_audit.py`: `runtime_llm_direct_http_hits = 0`
- `git diff --check`: passed

## Dev Eval Readiness

`ready_for_gemini_dev_eval=false`

Reason: dev eval must not run until Gemini smoke is 7/7. The post-fix Gemini smoke could not execute rows in this process because the pre-smoke toolcall probe returned HTML 400.
