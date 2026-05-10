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
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 32 | 3 | 0.4180 | 0.1719 | available | 1.3750 | 5529.9375 | {'measured_usage': 32} | 3.6360 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.4063 | 0.2257 | available | 1.4571 | 7883.1714 | {'measured_usage': 35} | 3.6192 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.4453 | 0.6333 | available | 1.4571 | 700.9429 | {'measured_usage': 35} | 1.9597 |

## Deterministic Comparison

- SQL_FIRST_API_VERIFY strict score: `0.6553`
- Comparison: `best_llm_strategy=LLM_CONTROLLER_OPTIMIZED_AGENT strict_delta=-0.022; deterministic SQL_FIRST_API_VERIFY remains preferred`

The SDK LLM baseline remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.
