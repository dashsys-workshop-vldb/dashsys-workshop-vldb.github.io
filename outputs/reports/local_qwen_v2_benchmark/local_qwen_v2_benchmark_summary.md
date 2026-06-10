# Local Qwen V2 Benchmark Summary

## Scope

- Provider: `openai` OpenAI-compatible local endpoint.
- Model: `[REDACTED]/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit`.
- Gemini used: `false`.
- Pioneer used: `false`.
- Packaged default unchanged: `SQL_FIRST_API_VERIFY`.
- V2 promoted: `false`.

## Smoke Gate

- passed_count: `7`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_final_failures: `0`

## Strict Dev Eval

| Strategy | Completed | Rows | Timeouts | Final | Correctness | Answer | SQL | API | Tool Calls | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` | True | 35 | 3 | 0.1761 | 0.2282 | 0.2017 | 0.0600 | 0.3209 | 0.8857 | 24.3339 |
| `SQL_FIRST_API_VERIFY` | True | 35 | 0 | 0.6563 | 0.6812 | 0.3223 | 0.9333 | 0.9791 | 1.4571 | 0.0176 |

## Objective Metrics

- timed_out_query_ids: `example_006, example_012, example_013`
- failed_query_ids: `example_006, example_012, example_013`
- compiled_sql_count: `20`
- compiled_api_count: `12`
- V2 SQL/API calls: `19` / `12`
- baseline SQL/API calls: `15` / `36`
- runtime_fact_count: `16`
- unsupported_claims: `0`
- no_tool_fp: `5`
- final_semantic_gate_initial_failures: `15`
- final_semantic_gate_final_failures: `12`
- local/live scope errors: `0`
- API_ERROR no-data misuse: `0`
- LIVE_EMPTY global absence misuse: `0`
- raw SQL fallback used count: `0`
- semantic alias count: `0`
- exact cache hits: `0`

## Gates And Validation

- Semantic route promotion gate: promotion_allowed=`False`, recommendation=`keep_shadow_only`.
- Integrated robustness gate recommendation: `promote_efficiency_recovery_fix`.
- Hidden-style eval cases: `48` (passed `48`, failed `0`).
- check_submission_ready ok: `True`; default SQL_FIRST: `True`; query outputs: `73`.
- SDK usage audit runtime_llm_direct_http_hits: `0`.
- pytest: `1158 passed, 1 skipped`.
- git diff --check: `passed`.

## Conclusion

V2 completed under local Qwen with per-query timeout and partial reporting, so the benchmark no longer hangs indefinitely. It is not promotable: it timed out on 3 public/dev rows and trails the packaged `SQL_FIRST_API_VERIFY` baseline on final/correctness/SQL/API/answer metrics. Keep V2 shadow-only and do not promote.
