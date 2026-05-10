# SDK LLM Baseline Evaluation Report

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
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
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 32 | 3 | 0.4180 | 0.172 | available | 1.3750 | 5529.9375 | {'measured_usage': 32} | 3.6138 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.4063 | 0.2256 | available | 1.4571 | 7883.1714 | {'measured_usage': 35} | 3.6358 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.4509 | 0.6341 | available | 1.4571 | 693.2857 | {'measured_usage': 35} | 1.8992 |

## Deterministic Comparison

- SQL_FIRST_API_VERIFY strict score: `0.6491`
- Comparison: `best_llm_strategy=LLM_CONTROLLER_OPTIMIZED_AGENT strict_delta=-0.015; deterministic SQL_FIRST_API_VERIFY remains preferred`

The SDK LLM baseline remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.
