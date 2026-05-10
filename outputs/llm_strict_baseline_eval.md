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
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1719 | 0.2427 | 0.2757 | 0.0000 | 0.3301 | 5887.6000 | {'measured_usage': 35} | 3.8115 | 1.4857 | -0.4834 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.2257 | 0.3119 | 0.2648 | 0.1200 | 0.4287 | 7883.1714 | {'measured_usage': 35} | 3.6192 | 1.4571 | -0.4296 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.6333 | 0.6639 | 0.2608 | 0.9333 | 0.9791 | 700.9429 | {'measured_usage': 35} | 1.9597 | 1.4571 | -0.0219 |
| `REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.1719 | 0.2427 | 0.2757 | 0.0000 | 0.3301 | 5887.6000 | {'measured_usage': 35} | 3.8115 | 1.4857 | -0.4834 |

## Recommendation

- Keep the SDK LLM baseline shadow-only unless a future explicit promotion runs strict, safety, hidden-style, package, and no-secret gates.
- Deterministic `SQL_FIRST_API_VERIFY` remains the packaged strategy.
