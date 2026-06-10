# SDK LLM Baseline Evaluation Report

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
- Transport: `openai_sdk`
- SDK path used: `True`
- SDK client: `SDK-based LLM client`
- Base URL: `https://photos-hewlett-safely-friends.trycloudflare.com/v1`
- Current LLM backend: `qwen2.5-32b-instruct`
- Smoke test passed: `True`
- Tool calling supported: `True`
- Strict scoring status: `available`
- Recommendation: `keep_shadow_only`
- Promotion status: `shadow_only`

The LLM baseline framework is generic; the configured model/provider is backend metadata.

## Strategy Summary

| Strategy | Rows | Valid runs | Failed runs | Avg answer score | Strict score | Strict status | Avg tools | Avg tokens | Token source | Avg runtime |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | ---: |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 34 | 1 | 0.4182 | 0.1596 | available | 1.4412 | 5704.9706 | {'measured_usage': 34} | 3.8197 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.4076 | 0.2244 | available | 1.4571 | 7879.3429 | {'measured_usage': 35} | 3.8873 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.4471 | 0.6328 | available | 1.4571 | 698.8286 | {'measured_usage': 35} | 2.2144 |

## Deterministic Comparison

- SQL_FIRST_API_VERIFY strict score: `0.6553`
- Comparison: `best_llm_strategy=LLM_CONTROLLER_OPTIMIZED_AGENT strict_delta=-0.0225; deterministic SQL_FIRST_API_VERIFY remains preferred`

The SDK LLM baseline remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.
