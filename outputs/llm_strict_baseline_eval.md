# SDK LLM Strict Baseline Evaluation

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
- Current LLM backend: `qwen2.5-32b-instruct`
- Smoke test passed: `True`
- Tool calling supported: `True`
- Strict scoring status: `available`
- Recommendation: `keep_shadow_only`

The LLM baseline framework is generic; the configured model/provider is backend metadata.

## Strategy Summary

| Strategy | Rows | Valid | Failed | Strict score | Correctness | Answer | SQL | API | Tokens | Token source | Runtime | Tools | Avg delta |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1720 | 0.2427 | 0.2757 | 0.0000 | 0.3301 | 5887.6000 | {'measured_usage': 35} | 3.7892 | 1.4857 | -0.4772 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.2256 | 0.3119 | 0.2648 | 0.1200 | 0.4287 | 7883.1714 | {'measured_usage': 35} | 3.6358 | 1.4571 | -0.4235 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.6341 | 0.6644 | 0.2618 | 0.9333 | 0.9791 | 693.2857 | {'measured_usage': 35} | 1.8992 | 1.4571 | -0.0151 |
| `REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1720 | 0.2427 | 0.2757 | 0.0000 | 0.3301 | 5887.6000 | {'measured_usage': 35} | 3.7892 | 1.4857 | -0.4772 |

## Recommendation

- Keep the SDK LLM baseline shadow-only unless a future explicit promotion runs strict, safety, hidden-style, package, and no-secret gates.
- Deterministic `SQL_FIRST_API_VERIFY` remains the packaged strategy.
