# V2 Non-GPT-4 Pioneer Model Benchmark Summary

## Purpose

This benchmark verifies V2 stability across callable non-GPT-4 Pioneer/API models. GPT-4/Gpt 4o family models are intentionally excluded.

## Model-Major Semantics

Each callable model runs the complete benchmark suite before the runner switches to the next model. No per-prompt model rotation is used.

## Excluded GPT-4 Family Models

- Reason: GPT-4/Gpt 4o family models are excluded from this non-GPT-4 stability benchmark.

| Display Name | Model ID | Reason |
| --- | --- | --- |

## Model Availability

| Display Name | Model ID | Available | Smoke | Benchmark | Error |
| --- | --- | ---: | --- | --- | --- |
| Qwen2.5 Coder 0.5b | `Qwen/Qwen2.5-Coder-0.5B` | False | False | not_run | provider_error |
| Qwen3 1.7B Base | `Qwen/Qwen3-1.7B-Base` | True | False | skipped_smoke_failed |  |
| Qwen3 235b A22b Instruct 2507 | `Qwen/Qwen3-235B-A22B-Instruct-2507` | False | False | not_run | provider_error |
| Qwen3 32B | `Qwen/Qwen3-32B` | True | False | skipped_smoke_failed |  |
| Qwen3 4B Base | `Qwen/Qwen3-4B-Base` | True | False | skipped_smoke_failed |  |
| Qwen3 4B Instruct 2507 | `Qwen/Qwen3-4B-Instruct-2507` | True | False | skipped_smoke_failed |  |
| Qwen3.5 9B | `Qwen/Qwen3.5-9B` | True | False | skipped_smoke_failed |  |
| Qwen3.6 27B | `Qwen/Qwen3.6-27B` | True | False | skipped_smoke_failed |  |
| Qwen3.6 35B A3B | `Qwen/Qwen3.6-35B-A3B` | True | False | skipped_smoke_failed |  |
| Qwen3.6 Flash | `qwen3.6-flash` | True | False | skipped_smoke_failed |  |
| Qwen3.6 Max Preview | `qwen3.6-max-preview` | True | False | skipped_smoke_failed |  |
| Qwen3.6 Plus | `qwen3.6-plus` | True | False | skipped_smoke_failed |  |
| Qwen3.7 Max | `qwen3.7-max` | True | False | skipped_smoke_failed |  |
| Qwen3 8B | `Qwen/Qwen3-8B` | True | False | skipped_smoke_failed |  |
| Claude 3 7 Sonnet Latest | `claude-3-7-sonnet-latest` | False | False | not_run | model_not_found |
| Claude Haiku 4.5 | `claude-haiku-4-5` | True | False | skipped_smoke_failed |  |
| Claude Opus 4.1 | `claude-opus-4-1` | True | False | skipped_smoke_failed |  |
| Claude Opus 4.5 | `claude-opus-4-5` | True | False | skipped_smoke_failed |  |
| Claude Opus 4.6 | `claude-opus-4-6` | True | False | skipped_smoke_failed |  |
| Claude Opus 4.7 | `claude-opus-4-7` | True | False | skipped_smoke_failed |  |
| Claude Opus 4.8 | `claude-opus-4-8` | True | False | skipped_smoke_failed |  |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | True | False | skipped_smoke_failed |  |
| Deepseek V3.1 | `deepseek-ai/DeepSeek-V3.1` | False | False | not_run | provider_error |
| DeepSeek V4 Flash | `deepseek-ai/DeepSeek-V4-Flash` | True | False | skipped_smoke_failed |  |
| DeepSeek V4 Pro | `deepseek-ai/DeepSeek-V4-Pro` | True | False | skipped_smoke_failed |  |
| Llama 3.1 70b | `llama-3.1-70b` | False | False | not_run | model_not_found |
| Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | True | False | skipped_smoke_failed |  |
| Llama 3.2 1b | `meta-llama/Llama-3.2-1B` | False | False | not_run | provider_error |
| Llama 3.2 1B Instruct | `meta-llama/Llama-3.2-1B-Instruct` | True | False | skipped_smoke_failed |  |
| Llama 3.2 3b | `meta-llama/Llama-3.2-3B` | False | False | not_run | provider_error |
| Llama 3.2 3B Instruct | `meta-llama/Llama-3.2-3B-Instruct` | True | False | skipped_smoke_failed |  |
| Llama 3.3 70B Instruct | `meta-llama/Llama-3.3-70B-Instruct` | True | False | skipped_smoke_failed |  |
| Mistral Nemo Instruct 2407 | `mistralai/Mistral-Nemo-Instruct-2407` | True | False | skipped_smoke_failed |  |
| Gemma 3 4B (Pretrained) | `google/gemma-3-4b-pt` | True | False | skipped_smoke_failed |  |
| Gemma 4 31B It | `google/gemma-4-31B-it` | False | False | not_run | timeout |
| Gemma 4 E2B IT | `google/gemma-4-E2B-it` | True | False | skipped_smoke_failed |  |
| Gemma 4 E4B It | `google/gemma-4-E4B-it` | False | False | not_run | timeout |
| MiniMax M2.7 | `MiniMaxAI/MiniMax-M2.7` | True | False | skipped_smoke_failed |  |
| Kimi K2.6 | `moonshotai/Kimi-K2.6` | True | False | skipped_smoke_failed |  |
| GLM 5.1 | `zai-org/GLM-5.1` | True | False | skipped_smoke_failed |  |
| MiMo V2.5 Pro | `XiaomiMiMo/MiMo-V2.5-Pro` | True | False | skipped_smoke_failed |  |
| GPT-OSS 120B | `openai/gpt-oss-120b` | True | False | skipped_smoke_failed |  |
| GPT-OSS 20B | `openai/gpt-oss-20b` | True | False | skipped_smoke_failed |  |
| Gemini 3.5 Flash | `gemini-3.5-flash` | True | False | skipped_smoke_failed |  |
| GPT-5.1 | `gpt-5.1` | False | False | not_run | provider_error |
| GPT-5.4 | `gpt-5.4` | True | False | skipped_smoke_failed |  |
| GPT-5.4 mini | `gpt-5.4-mini` | True | False | skipped_smoke_failed |  |
| GPT-5.4 nano | `gpt-5.4-nano` | True | False | skipped_smoke_failed |  |
| GPT-5.5 | `gpt-5.5` | False | False | not_run | provider_error |
| GPT-5 mini | `gpt-5-mini` | True | False | skipped_smoke_failed |  |
| GPT-5 nano | `gpt-5-nano` | True | False | skipped_smoke_failed |  |
| LFM2 24B A2B | `LiquidAI/LFM2-24B-A2B` | True | False | skipped_smoke_failed |  |
| SmolLM3 3B Base | `HuggingFaceTB/SmolLM3-3B-Base` | True | False | skipped_smoke_failed |  |

## Per-Model Benchmark Scores

| Model | Verdict | Org35 Final | Org35 Correctness | Org35 Answer | Org35 SQL | Org35 API | Org35 Tool Calls | Internal50 Combined | Internal50 Behavior |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 Coder 0.5b | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Qwen3 1.7B Base | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3 235b A22b Instruct 2507 | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Qwen3 32B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3 4B Base | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3 4B Instruct 2507 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.5 9B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.6 27B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.6 35B A3B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.6 Flash | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.6 Max Preview | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.6 Plus | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3.7 Max | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Qwen3 8B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude 3 7 Sonnet Latest | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Claude Haiku 4.5 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Opus 4.1 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Opus 4.5 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Opus 4.6 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Opus 4.7 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Opus 4.8 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Claude Sonnet 4.6 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Deepseek V3.1 | UNAVAILABLE |  |  |  |  |  |  |  |  |
| DeepSeek V4 Flash | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| DeepSeek V4 Pro | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Llama 3.1 70b | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Llama 3.1 8B Instruct | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Llama 3.2 1b | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Llama 3.2 1B Instruct | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Llama 3.2 3b | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Llama 3.2 3B Instruct | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Llama 3.3 70B Instruct | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Mistral Nemo Instruct 2407 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Gemma 3 4B (Pretrained) | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Gemma 4 31B It | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Gemma 4 E2B IT | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Gemma 4 E4B It | UNAVAILABLE |  |  |  |  |  |  |  |  |
| MiniMax M2.7 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Kimi K2.6 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GLM 5.1 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| MiMo V2.5 Pro | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-OSS 120B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-OSS 20B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| Gemini 3.5 Flash | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-5.1 | UNAVAILABLE |  |  |  |  |  |  |  |  |
| GPT-5.4 | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-5.4 mini | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-5.4 nano | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-5.5 | UNAVAILABLE |  |  |  |  |  |  |  |  |
| GPT-5 mini | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| GPT-5 nano | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| LFM2 24B A2B | SMOKE_FAILED |  |  |  |  |  |  |  |  |
| SmolLM3 3B Base | SMOKE_FAILED |  |  |  |  |  |  |  |  |

## Model Usage

| Model | Active Provider | Model ID | LLM Calls | Semantic Calls | Direct Answer Calls | JSON Failures | Evidence Fallbacks |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 Coder 0.5b | pioneer_chat | `Qwen/Qwen2.5-Coder-0.5B` | 0 | 0 | 0 | 0 | 0 |
| Qwen3 1.7B Base | pioneer_chat | `Qwen/Qwen3-1.7B-Base` | 7 | 7 | 0 | 5 | 5 |
| Qwen3 235b A22b Instruct 2507 | pioneer_chat | `Qwen/Qwen3-235B-A22B-Instruct-2507` | 0 | 0 | 0 | 0 | 0 |
| Qwen3 32B | pioneer_chat | `Qwen/Qwen3-32B` | 7 | 7 | 0 | 7 | 7 |
| Qwen3 4B Base | pioneer_chat | `Qwen/Qwen3-4B-Base` | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Instruct 2507 | pioneer_chat | `Qwen/Qwen3-4B-Instruct-2507` | 7 | 7 | 0 | 7 | 7 |
| Qwen3.5 9B | pioneer_chat | `Qwen/Qwen3.5-9B` | 7 | 7 | 0 | 7 | 7 |
| Qwen3.6 27B | pioneer_chat | `Qwen/Qwen3.6-27B` | 7 | 7 | 0 | 7 | 7 |
| Qwen3.6 35B A3B | pioneer_chat | `Qwen/Qwen3.6-35B-A3B` | 7 | 7 | 0 | 7 | 7 |
| Qwen3.6 Flash | pioneer_chat | `qwen3.6-flash` | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Max Preview | pioneer_chat | `qwen3.6-max-preview` | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Plus | pioneer_chat | `qwen3.6-plus` | 0 | 0 | 0 | 0 | 0 |
| Qwen3.7 Max | pioneer_chat | `qwen3.7-max` | 0 | 0 | 0 | 0 | 0 |
| Qwen3 8B | pioneer_chat | `Qwen/Qwen3-8B` | 7 | 7 | 0 | 0 | 0 |
| Claude 3 7 Sonnet Latest | pioneer_chat | `claude-3-7-sonnet-latest` | 0 | 0 | 0 | 0 | 0 |
| Claude Haiku 4.5 | pioneer_chat | `claude-haiku-4-5` | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.1 | pioneer_chat | `claude-opus-4-1` | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.5 | pioneer_chat | `claude-opus-4-5` | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.6 | pioneer_chat | `claude-opus-4-6` | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.7 | pioneer_chat | `claude-opus-4-7` | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.8 | pioneer_chat | `claude-opus-4-8` | 0 | 0 | 0 | 0 | 0 |
| Claude Sonnet 4.6 | pioneer_chat | `claude-sonnet-4-6` | 0 | 0 | 0 | 0 | 0 |
| Deepseek V3.1 | pioneer_chat | `deepseek-ai/DeepSeek-V3.1` | 0 | 0 | 0 | 0 | 0 |
| DeepSeek V4 Flash | pioneer_chat | `deepseek-ai/DeepSeek-V4-Flash` | 7 | 7 | 0 | 7 | 7 |
| DeepSeek V4 Pro | pioneer_chat | `deepseek-ai/DeepSeek-V4-Pro` | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 70b | pioneer_chat | `llama-3.1-70b` | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 8B Instruct | pioneer_chat | `meta-llama/Llama-3.1-8B-Instruct` | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 1b | pioneer_chat | `meta-llama/Llama-3.2-1B` | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 1B Instruct | pioneer_chat | `meta-llama/Llama-3.2-1B-Instruct` | 7 | 7 | 0 | 7 | 7 |
| Llama 3.2 3b | pioneer_chat | `meta-llama/Llama-3.2-3B` | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 3B Instruct | pioneer_chat | `meta-llama/Llama-3.2-3B-Instruct` | 7 | 7 | 0 | 7 | 7 |
| Llama 3.3 70B Instruct | pioneer_chat | `meta-llama/Llama-3.3-70B-Instruct` | 7 | 7 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | pioneer_chat | `mistralai/Mistral-Nemo-Instruct-2407` | 7 | 7 | 0 | 0 | 0 |
| Gemma 3 4B (Pretrained) | pioneer_chat | `google/gemma-3-4b-pt` | 7 | 7 | 0 | 7 | 7 |
| Gemma 4 31B It | pioneer_chat | `google/gemma-4-31B-it` | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E2B IT | pioneer_chat | `google/gemma-4-E2B-it` | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E4B It | pioneer_chat | `google/gemma-4-E4B-it` | 0 | 0 | 0 | 0 | 0 |
| MiniMax M2.7 | pioneer_chat | `MiniMaxAI/MiniMax-M2.7` | 7 | 7 | 0 | 7 | 7 |
| Kimi K2.6 | pioneer_chat | `moonshotai/Kimi-K2.6` | 7 | 7 | 0 | 7 | 7 |
| GLM 5.1 | pioneer_chat | `zai-org/GLM-5.1` | 7 | 7 | 0 | 7 | 7 |
| MiMo V2.5 Pro | pioneer_chat | `XiaomiMiMo/MiMo-V2.5-Pro` | 7 | 7 | 0 | 7 | 7 |
| GPT-OSS 120B | pioneer_chat | `openai/gpt-oss-120b` | 7 | 7 | 0 | 7 | 7 |
| GPT-OSS 20B | pioneer_chat | `openai/gpt-oss-20b` | 7 | 7 | 0 | 7 | 7 |
| Gemini 3.5 Flash | pioneer_chat | `gemini-3.5-flash` | 7 | 7 | 0 | 7 | 7 |
| GPT-5.1 | pioneer_chat | `gpt-5.1` | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 | pioneer_chat | `gpt-5.4` | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 mini | pioneer_chat | `gpt-5.4-mini` | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 nano | pioneer_chat | `gpt-5.4-nano` | 0 | 0 | 0 | 0 | 0 |
| GPT-5.5 | pioneer_chat | `gpt-5.5` | 0 | 0 | 0 | 0 | 0 |
| GPT-5 mini | pioneer_chat | `gpt-5-mini` | 0 | 0 | 0 | 0 | 0 |
| GPT-5 nano | pioneer_chat | `gpt-5-nano` | 7 | 7 | 0 | 7 | 7 |
| LFM2 24B A2B | pioneer_chat | `LiquidAI/LFM2-24B-A2B` | 0 | 0 | 0 | 0 | 0 |
| SmolLM3 3B Base | pioneer_chat | `HuggingFaceTB/SmolLM3-3B-Base` | 7 | 7 | 0 | 7 | 7 |

## Safety

| Model | no_tool_fp | api_required_underuse | unsupported_claims | concrete_data_llm_direct | JSON failures | Semantic fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 Coder 0.5b | None | None | None | None | None | None |
| Qwen3 1.7B Base | 0 | 0 | 0 | 0 | 5 | 5 |
| Qwen3 235b A22b Instruct 2507 | None | None | None | None | None | None |
| Qwen3 32B | 0 | 0 | 0 | 0 | 7 | 7 |
| Qwen3 4B Base | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Instruct 2507 | 0 | 0 | 0 | 0 | 7 | 7 |
| Qwen3.5 9B | 0 | 0 | 0 | 0 | 7 | 7 |
| Qwen3.6 27B | 0 | 0 | 0 | 0 | 7 | 7 |
| Qwen3.6 35B A3B | 0 | 0 | 0 | 0 | 7 | 7 |
| Qwen3.6 Flash | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Max Preview | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Plus | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.7 Max | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 8B | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude 3 7 Sonnet Latest | None | None | None | None | None | None |
| Claude Haiku 4.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.8 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Sonnet 4.6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Deepseek V3.1 | None | None | None | None | None | None |
| DeepSeek V4 Flash | 0 | 0 | 0 | 0 | 7 | 7 |
| DeepSeek V4 Pro | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 70b | None | None | None | None | None | None |
| Llama 3.1 8B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 1b | None | None | None | None | None | None |
| Llama 3.2 1B Instruct | 0 | 0 | 0 | 0 | 7 | 7 |
| Llama 3.2 3b | None | None | None | None | None | None |
| Llama 3.2 3B Instruct | 0 | 0 | 0 | 0 | 7 | 7 |
| Llama 3.3 70B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 3 4B (Pretrained) | 0 | 0 | 0 | 0 | 7 | 7 |
| Gemma 4 31B It | None | None | None | None | None | None |
| Gemma 4 E2B IT | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E4B It | None | None | None | None | None | None |
| MiniMax M2.7 | 0 | 0 | 0 | 0 | 7 | 7 |
| Kimi K2.6 | 0 | 0 | 0 | 0 | 7 | 7 |
| GLM 5.1 | 0 | 0 | 0 | 0 | 7 | 7 |
| MiMo V2.5 Pro | 0 | 0 | 0 | 0 | 7 | 7 |
| GPT-OSS 120B | 0 | 0 | 0 | 0 | 7 | 7 |
| GPT-OSS 20B | 0 | 0 | 0 | 0 | 7 | 7 |
| Gemini 3.5 Flash | 0 | 0 | 0 | 0 | 7 | 7 |
| GPT-5.1 | None | None | None | None | None | None |
| GPT-5.4 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 mini | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 nano | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.5 | None | None | None | None | None | None |
| GPT-5 mini | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5 nano | 0 | 0 | 0 | 0 | 7 | 7 |
| LFM2 24B A2B | 0 | 0 | 0 | 0 | 0 | 0 |
| SmolLM3 3B Base | 0 | 0 | 0 | 0 | 7 | 7 |

## Routing / Evidence

| Model | LLM_DIRECT | LLM_SAFE_DIRECT | Evidence Pipeline | Bypassed | EvidenceBus Built | Post-Evidence Router |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 Coder 0.5b | None | None | None | None | None | None |
| Qwen3 1.7B Base | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 235b A22b Instruct 2507 | None | None | None | None | None | None |
| Qwen3 32B | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Base | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Instruct 2507 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5 9B | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 27B | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 35B A3B | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Flash | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Max Preview | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Plus | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.7 Max | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 8B | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude 3 7 Sonnet Latest | None | None | None | None | None | None |
| Claude Haiku 4.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.8 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Sonnet 4.6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Deepseek V3.1 | None | None | None | None | None | None |
| DeepSeek V4 Flash | 0 | 0 | 0 | 0 | 0 | 0 |
| DeepSeek V4 Pro | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 70b | None | None | None | None | None | None |
| Llama 3.1 8B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 1b | None | None | None | None | None | None |
| Llama 3.2 1B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 3b | None | None | None | None | None | None |
| Llama 3.2 3B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.3 70B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 3 4B (Pretrained) | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 31B It | None | None | None | None | None | None |
| Gemma 4 E2B IT | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E4B It | None | None | None | None | None | None |
| MiniMax M2.7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Kimi K2.6 | 0 | 0 | 0 | 0 | 0 | 0 |
| GLM 5.1 | 0 | 0 | 0 | 0 | 0 | 0 |
| MiMo V2.5 Pro | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-OSS 120B | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-OSS 20B | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemini 3.5 Flash | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.1 | None | None | None | None | None | None |
| GPT-5.4 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 mini | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 nano | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.5 | None | None | None | None | None | None |
| GPT-5 mini | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5 nano | 0 | 0 | 0 | 0 | 0 | 0 |
| LFM2 24B A2B | 0 | 0 | 0 | 0 | 0 | 0 |
| SmolLM3 3B Base | 0 | 0 | 0 | 0 | 0 | 0 |

## Cross-Model Conclusion

- Callable models: 42
- Completed full benchmark models: none
- Unavailable models: Qwen2.5 Coder 0.5b, Qwen3 235b A22b Instruct 2507, Claude 3 7 Sonnet Latest, Deepseek V3.1, Llama 3.1 70b, Llama 3.2 1b, Llama 3.2 3b, Gemma 4 31B It, Gemma 4 E4B It, GPT-5.1, GPT-5.5
- Unsafe models: none
- V2 stable across callable models: True
- Weak malformed responses failed closed: True

No recommendation is made to continue with only the best model; this report is about system robustness across model families.
