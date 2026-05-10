# SDK LLM Strict Baseline Evaluation

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
- Current LLM backend: `qwen2.5-32b-instruct`
- Smoke test passed: `False`
- Tool calling supported: `False`
- Strict scoring status: `available`
- Recommendation: `keep_shadow_only`

The LLM baseline framework is generic; the configured model/provider is backend metadata.

## Strategy Summary

| Strategy | Rows | Valid | Failed | Strict score | Correctness | Answer | SQL | API | Tokens | Token source | Runtime | Tools | Avg delta |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.3411 | 0.3646 | 0.8500 | 0.0000 | 0.0000 | 2265.6000 | {'estimated': 35} | 1.3892 | 0.0000 | -0.3141 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.3335 | 0.3646 | 0.8500 | 0.0000 | 0.0000 | 3182.6000 | {'estimated': 35} | 1.3707 | 0.0000 | -0.3217 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.6336 | 0.6610 | 0.2573 | 0.9333 | 0.9791 | 545.0857 | {'estimated': 35} | 1.3950 | 1.4571 | -0.0216 |
| `REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.3411 | 0.3646 | 0.8500 | 0.0000 | 0.0000 | 2265.6000 | {'estimated': 35} | 1.3892 | 0.0000 | -0.3141 |

## Recommendation

- Keep the SDK LLM baseline shadow-only unless a future explicit promotion runs strict, safety, hidden-style, package, and no-secret gates.
- Deterministic `SQL_FIRST_API_VERIFY` remains the packaged strategy.
