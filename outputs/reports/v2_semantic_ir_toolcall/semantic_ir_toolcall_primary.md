# V2 Semantic IR Toolcall Primary Report

## Summary

- Implemented SDK toolcall-first Semantic IR planner for `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`.
- Packaged default remains `SQL_FIRST_API_VERIFY`.
- V2 is not promoted.
- Pioneer was not used for the Hermes probe or smoke path.
- Atomic/text protocol remains fallback/diagnostic only.

## Files Changed

- `dashagent/v2_semantic_ir.py`
- `dashagent/v2_semantic_ir_context.py`
- `dashagent/v2_semantic_ir_validator.py`
- `dashagent/v2_semantic_ir_compiler.py`
- `dashagent/v2_semantic_ir_planner.py`
- `dashagent/llm_unified_planner.py`
- `scripts/probe_hermes_sdk_toolcall.py`
- `scripts/run_hermes_v2_toolcall_smoke.py`
- `tests/test_v2_semantic_ir.py`
- `tests/test_hermes_toolcall_probe.py`
- `tests/test_v2_structured_tool_output.py`

## LLM Tool Schema

Primary SDK tool: `submit_semantic_ir_plan`.

The LLM owns:

- `DIRECT` vs `EVIDENCE`
- task decomposition
- operation/source/kind
- table and endpoint selection from allowed context cards
- fields, filters, values, dependencies
- aggregation instruction

The backend only validates shape/existence and mechanically compiles valid IR.

## Backend Boundary

- Backend semantic planning used: `false`
- Backend formal compilation used for valid Semantic IR: `true`
- Backend does not infer missing tables, endpoints, fields, filters, or intent.
- Unknown tables/endpoints/fields fail validation and trigger one SDK toolcall repair attempt.
- Existing SQLCompileGate and APIRequestGate still run after compilation.

## Trace Fields

Implemented planner diagnostics:

- `sdk_toolcall_semantic_ir_used`
- `semantic_ir_toolcall_supported`
- `semantic_ir_validation_passed`
- `semantic_ir_validation_error_type`
- `semantic_ir_validation_error_message`
- `semantic_ir_repair_attempted`
- `semantic_ir_repair_success`
- `backend_formal_compilation_used`
- `backend_semantic_planning_used`
- `backend_sql_api_generation_used`
- `atomic_protocol_fallback_used`
- `compiled_sql_count`
- `compiled_api_count`
- `planner_parse_source`

## Hermes Configuration / Probe

- Provider used for explicit probe rerun: `openai`
- SDK path used: `true`
- OpenAI-compatible base URL present: `true`
- OpenAI API key present: `true`
- Toolcall supported: `false`
- Tool calls count: `0`
- Finish reason: `stop`
- Probe result: model responded through SDK but returned content only; no native SDK tool call was returned.

Probe report:

- `outputs/reports/hermes_toolcall_probe/hermes_toolcall_probe.md`
- `outputs/reports/hermes_toolcall_probe/hermes_toolcall_probe.json`

## Focused Smoke

Smoke report was generated but skipped because the Hermes/OpenAI-compatible endpoint did not return native SDK tool calls in the probe.

Smoke report:

- `outputs/reports/hermes_v2_toolcall_smoke/hermes_v2_toolcall_smoke.md`
- `outputs/reports/hermes_v2_toolcall_smoke/hermes_v2_toolcall_smoke.json`

## Benchmark

Not run. The focused Hermes SDK toolcall smoke did not run because the probe failed native toolcall support.

## Validation

- `python3 -m pytest -q`: `1085 passed, 1 skipped`
- `python3 scripts/check_submission_ready.py`: `ok=true`, packaged default `SQL_FIRST_API_VERIFY`, query output count `73`, secret scan clean
- `python3 scripts/generate_sdk_usage_audit.py`: `runtime_llm_direct_http_hits=0`
- `git diff --check`: passed

## Recommendation

- Safe to keep: yes
- Safe to commit: yes, subject to normal review of generated report artifacts
- Safe to promote V2: no

Promotion is not appropriate because Hermes native SDK toolcall support was not confirmed in this environment, and the focused smoke/benchmark were intentionally not run.
