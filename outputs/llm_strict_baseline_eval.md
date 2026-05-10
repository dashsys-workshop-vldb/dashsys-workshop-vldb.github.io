# SDK LLM Strict Baseline Evaluation

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
- Transport: `openai_sdk`
- SDK path used: `True`
- Current LLM backend: `qwen2.5-32b-instruct`
- Smoke test passed: `True`
- Tool calling supported: `True`
- Strict scoring status: `available`
- Recommendation: `keep_shadow_only`

The LLM baseline framework is generic; the configured model/provider is backend metadata.

## Strategy Summary

| Strategy | Rows | Valid | Failed | Strict score | Correctness | Answer | SQL | API | Tokens | Token source | Runtime | Tools | Avg delta |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1594 | 0.2307 | 0.2337 | 0.0000 | 0.3397 | 5817.6000 | {'measured_usage': 35} | 3.9720 | 1.4571 | -0.4958 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.2245 | 0.3111 | 0.2631 | 0.1200 | 0.4287 | 7879.3429 | {'measured_usage': 35} | 3.8653 | 1.4571 | -0.4308 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.6331 | 0.6640 | 0.2609 | 0.9333 | 0.9791 | 700.2571 | {'measured_usage': 35} | 2.0533 | 1.4571 | -0.0221 |
| `REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1594 | 0.2307 | 0.2337 | 0.0000 | 0.3397 | 5817.6000 | {'measured_usage': 35} | 3.9720 | 1.4571 | -0.4958 |

## Recommendation

- Keep the SDK LLM baseline shadow-only unless a future explicit promotion runs strict, safety, hidden-style, package, and no-secret gates.
- Deterministic `SQL_FIRST_API_VERIFY` remains the packaged strategy.
