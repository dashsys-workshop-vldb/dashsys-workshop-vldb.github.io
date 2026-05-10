# Qwen LLM Baseline Evaluation Report

- Provider: `openai_compatible_qwen`
- Base URL: `https://photos-hewlett-safely-friends.trycloudflare.com/v1`
- Model: `qwen2.5-32b-instruct`
- Smoke test passed: `True`
- Tool calling supported: `True`
- Recommendation: `keep_shadow_only`
- Promotion status: `shadow_only`

## Strategy Summary

| Strategy | Rows | Valid runs | Failed runs | Avg answer score | Strict score | Avg tools | Avg tokens | Avg runtime |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 32 | 3 | 0.4180 | unavailable | 1.3750 | 1317.4688 | 3.5672 |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 35 | 0 | 0.4071 | unavailable | 1.4571 | 2057.3429 | 3.6183 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 35 | 0 | 0.4526 | unavailable | 1.4571 | 0.0000 | 1.9033 |

## Deterministic Comparison

- SQL_FIRST_API_VERIFY strict score: `0.6491`
- Comparison: `qwen_strict_score_unavailable; deterministic SQL_FIRST_API_VERIFY remains preferred`

Qwen remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.
