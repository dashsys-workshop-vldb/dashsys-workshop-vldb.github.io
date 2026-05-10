# SDK LLM Baseline Evaluation Report

- Framework: `generic_sdk_llm_baseline`
- Provider type: `openai_compatible`
- Backend type: `openai_sdk`
- SDK client: `SDK-based LLM client`
- Base URL: `https://photos-hewlett-safely-friends.trycloudflare.com/v1`
- Current LLM backend: `qwen2.5-32b-instruct`
- Smoke test passed: `False`
- Tool calling supported: `False`
- Strict scoring status: `available`
- Recommendation: `keep_shadow_only`
- Promotion status: `shadow_only`

The LLM baseline framework is generic; the configured model/provider is backend metadata.

## Strategy Summary

| Strategy | Rows | Valid runs | Failed runs | Avg answer score | Strict score | Strict status | Avg tools | Avg tokens | Token source | Avg runtime |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | ---: |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 0 | 35 | unavailable | 0.3411 | available | unavailable | unavailable | {} | unavailable |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 0 | 35 | unavailable | 0.3335 | available | unavailable | unavailable | {} | unavailable |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.4692 | 0.6336 | available | 1.4571 | 545.0857 | {'estimated': 35} | 1.3950 |

## Deterministic Comparison

- SQL_FIRST_API_VERIFY strict score: `0.6553`
- Comparison: `best_llm_strategy=LLM_CONTROLLER_OPTIMIZED_AGENT strict_delta=-0.0217; deterministic SQL_FIRST_API_VERIFY remains preferred`

The SDK LLM baseline remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.
