# V2 Non-GPT-4 Pioneer Model Benchmark

## Purpose

This benchmark tests V2 stability across callable non-GPT-4 Pioneer/API models. GPT-4 family was intentionally excluded.

## Excluded GPT-4 Models

| Display Name | Model ID | Reason |
| --- | --- | --- |
| Gpt 4.1 | `None` | excluded_gpt4_family_or_unavailable |
| Gpt 4.1 Mini | `None` | excluded_gpt4_family_or_unavailable |
| Gpt 4.1 Nano | `None` | excluded_gpt4_family_or_unavailable |
| Gpt 4o | `None` | excluded_gpt4_family_or_unavailable |
| Gpt 4o Mini | `None` | excluded_gpt4_family_or_unavailable |
| gpt-4.1 | `None` | excluded_gpt4_family_or_unavailable |
| gpt-4.1-mini | `None` | excluded_gpt4_family_or_unavailable |
| gpt-4.1-nano | `None` | excluded_gpt4_family_or_unavailable |
| gpt-4o | `None` | excluded_gpt4_family_or_unavailable |
| gpt-4o-mini | `None` | excluded_gpt4_family_or_unavailable |
| GPT-4.1 | `gpt-4.1` | excluded_gpt4_family_or_unavailable |
| GPT-4.1 mini | `gpt-4.1-mini` | excluded_gpt4_family_or_unavailable |
| GPT-4.1 nano | `gpt-4.1-nano` | excluded_gpt4_family_or_unavailable |
| GPT-4o | `gpt-4o` | excluded_gpt4_family_or_unavailable |
| GPT-4o mini | `gpt-4o-mini` | excluded_gpt4_family_or_unavailable |
| Gpt 4.1 | `gpt-4.1` | excluded_gpt4_family_or_unavailable |
| Gpt 4.1 Mini | `gpt-4.1-mini` | excluded_gpt4_family_or_unavailable |
| Gpt 4.1 Nano | `gpt-4.1-nano` | excluded_gpt4_family_or_unavailable |
| Gpt 4o | `gpt-4o` | excluded_gpt4_family_or_unavailable |
| Gpt 4o Mini | `gpt-4o-mini` | excluded_gpt4_family_or_unavailable |

## Candidate Models

| Display Name | Model ID | Family | Available | Smoke | Benchmark |
| --- | --- | --- | ---: | --- | --- |
| Qwen2.5 Coder 0.5b | `Qwen/Qwen2.5-Coder-0.5B` | qwen | False | failed | not_run |
| Qwen3 1.7B Base | `Qwen/Qwen3-1.7B-Base` | qwen | True | failed | skipped_smoke_failed |
| Qwen3 235b A22b Instruct 2507 | `Qwen/Qwen3-235B-A22B-Instruct-2507` | qwen | False | failed | not_run |
| Qwen3 32B | `Qwen/Qwen3-32B` | qwen | True | failed | skipped_smoke_failed |
| Qwen3 4B Base | `Qwen/Qwen3-4B-Base` | qwen | True | failed | skipped_smoke_failed |
| Qwen3 4B Instruct 2507 | `Qwen/Qwen3-4B-Instruct-2507` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.5 9B | `Qwen/Qwen3.5-9B` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.6 27B | `Qwen/Qwen3.6-27B` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.6 35B A3B | `Qwen/Qwen3.6-35B-A3B` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.6 Flash | `qwen3.6-flash` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.6 Max Preview | `qwen3.6-max-preview` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.6 Plus | `qwen3.6-plus` | qwen | True | failed | skipped_smoke_failed |
| Qwen3.7 Max | `qwen3.7-max` | qwen | True | failed | skipped_smoke_failed |
| Qwen3 8B | `Qwen/Qwen3-8B` | qwen | True | failed | skipped_smoke_failed |
| Claude 3 7 Sonnet Latest | `claude-3-7-sonnet-latest` | claude | False | failed | not_run |
| Claude Haiku 4.5 | `claude-haiku-4-5` | claude | True | failed | skipped_smoke_failed |
| Claude Opus 4.1 | `claude-opus-4-1` | claude | True | failed | skipped_smoke_failed |
| Claude Opus 4.5 | `claude-opus-4-5` | claude | True | failed | skipped_smoke_failed |
| Claude Opus 4.6 | `claude-opus-4-6` | claude | True | failed | skipped_smoke_failed |
| Claude Opus 4.7 | `claude-opus-4-7` | claude | True | failed | skipped_smoke_failed |
| Claude Opus 4.8 | `claude-opus-4-8` | claude | True | failed | skipped_smoke_failed |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | claude | True | failed | skipped_smoke_failed |
| Deepseek V3.1 | `deepseek-ai/DeepSeek-V3.1` | deepseek | False | failed | not_run |
| DeepSeek V4 Flash | `deepseek-ai/DeepSeek-V4-Flash` | deepseek | True | failed | skipped_smoke_failed |
| DeepSeek V4 Pro | `deepseek-ai/DeepSeek-V4-Pro` | deepseek | True | failed | skipped_smoke_failed |
| Llama 3.1 70b | `llama-3.1-70b` | llama | False | failed | not_run |
| Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | llama | True | failed | skipped_smoke_failed |
| Llama 3.2 1b | `meta-llama/Llama-3.2-1B` | llama | False | failed | not_run |
| Llama 3.2 1B Instruct | `meta-llama/Llama-3.2-1B-Instruct` | llama | True | failed | skipped_smoke_failed |
| Llama 3.2 3b | `meta-llama/Llama-3.2-3B` | llama | False | failed | not_run |
| Llama 3.2 3B Instruct | `meta-llama/Llama-3.2-3B-Instruct` | llama | True | failed | skipped_smoke_failed |
| Llama 3.3 70B Instruct | `meta-llama/Llama-3.3-70B-Instruct` | llama | True | failed | skipped_smoke_failed |
| Mistral Nemo Instruct 2407 | `mistralai/Mistral-Nemo-Instruct-2407` | mistral | True | failed | skipped_smoke_failed |
| Gemma 3 4B (Pretrained) | `google/gemma-3-4b-pt` | gemma | True | failed | skipped_smoke_failed |
| Gemma 4 31B It | `google/gemma-4-31B-it` | gemma | False | failed | not_run |
| Gemma 4 E2B IT | `google/gemma-4-E2B-it` | gemma | True | failed | skipped_smoke_failed |
| Gemma 4 E4B It | `google/gemma-4-E4B-it` | gemma | False | failed | not_run |
| MiniMax M2.7 | `MiniMaxAI/MiniMax-M2.7` | minimax | True | failed | skipped_smoke_failed |
| Kimi K2.6 | `moonshotai/Kimi-K2.6` | kimi | True | failed | skipped_smoke_failed |
| GLM 5.1 | `zai-org/GLM-5.1` | glm | True | failed | skipped_smoke_failed |
| MiMo V2.5 Pro | `XiaomiMiMo/MiMo-V2.5-Pro` | mimo | True | failed | skipped_smoke_failed |
| GPT-OSS 120B | `openai/gpt-oss-120b` | gpt_oss | True | failed | skipped_smoke_failed |
| GPT-OSS 20B | `openai/gpt-oss-20b` | gpt_oss | True | failed | skipped_smoke_failed |
| Gemini 3.5 Flash | `gemini-3.5-flash` | other | True | failed | skipped_smoke_failed |
| GPT-5.1 | `gpt-5.1` | other | False | failed | not_run |
| GPT-5.4 | `gpt-5.4` | other | True | failed | skipped_smoke_failed |
| GPT-5.4 mini | `gpt-5.4-mini` | other | True | failed | skipped_smoke_failed |
| GPT-5.4 nano | `gpt-5.4-nano` | other | True | failed | skipped_smoke_failed |
| GPT-5.5 | `gpt-5.5` | other | False | failed | not_run |
| GPT-5 mini | `gpt-5-mini` | other | True | failed | skipped_smoke_failed |
| GPT-5 nano | `gpt-5-nano` | other | True | failed | skipped_smoke_failed |
| LFM2 24B A2B | `LiquidAI/LFM2-24B-A2B` | other | True | failed | skipped_smoke_failed |
| SmolLM3 3B Base | `HuggingFaceTB/SmolLM3-3B-Base` | other | True | failed | skipped_smoke_failed |

## Per-Model Objective Results

| Model | Available | Smoke | Benchmark | SQL Calls | API Calls | EvidenceBus Non-Empty | Unsupported | no_tool_fp | Final Syntax Gate Failures | Final Semantic Gate Failures |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 Coder 0.5b | False | False | None | None | None | None | None | None | None | None |
| Qwen3 1.7B Base | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 235b A22b Instruct 2507 | False | False | None | None | None | None | None | None | None | None |
| Qwen3 32B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Base | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 4B Instruct 2507 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5 9B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 27B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 35B A3B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Flash | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Max Preview | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.6 Plus | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.7 Max | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3 8B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude 3 7 Sonnet Latest | False | False | None | None | None | None | None | None | None | None |
| Claude Haiku 4.5 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.1 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.5 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.6 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.7 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Opus 4.8 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Claude Sonnet 4.6 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Deepseek V3.1 | False | False | None | None | None | None | None | None | None | None |
| DeepSeek V4 Flash | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DeepSeek V4 Pro | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 70b | False | False | None | None | None | None | None | None | None | None |
| Llama 3.1 8B Instruct | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 1b | False | False | None | None | None | None | None | None | None | None |
| Llama 3.2 1B Instruct | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.2 3b | False | False | None | None | None | None | None | None | None | None |
| Llama 3.2 3B Instruct | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Llama 3.3 70B Instruct | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 3 4B (Pretrained) | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 31B It | False | False | None | None | None | None | None | None | None | None |
| Gemma 4 E2B IT | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E4B It | False | False | None | None | None | None | None | None | None | None |
| MiniMax M2.7 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Kimi K2.6 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GLM 5.1 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| MiMo V2.5 Pro | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-OSS 120B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-OSS 20B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemini 3.5 Flash | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.1 | False | False | None | None | None | None | None | None | None | None |
| GPT-5.4 | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 mini | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.4 nano | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5.5 | False | False | None | None | None | None | None | None | None | None |
| GPT-5 mini | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GPT-5 nano | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| LFM2 24B A2B | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| SmolLM3 3B Base | True | False | skipped_smoke_failed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Failure Analysis By Objective Error Type

- Qwen2.5 Coder 0.5b: provider_error
- Qwen3 1.7B Base: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3 235b A22b Instruct 2507: provider_error
- Qwen3 32B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3 4B Base: planner_toolcall_failure, empty EvidenceBus
- Qwen3 4B Instruct 2507: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3.5 9B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3.6 27B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3.6 35B A3B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Qwen3.6 Flash: planner_toolcall_failure, empty EvidenceBus
- Qwen3.6 Max Preview: planner_toolcall_failure, empty EvidenceBus
- Qwen3.6 Plus: planner_toolcall_failure, empty EvidenceBus
- Qwen3.7 Max: planner_toolcall_failure, empty EvidenceBus
- Qwen3 8B: planner_toolcall_failure, empty EvidenceBus
- Claude 3 7 Sonnet Latest: provider_error
- Claude Haiku 4.5: planner_toolcall_failure, empty EvidenceBus
- Claude Opus 4.1: planner_toolcall_failure, empty EvidenceBus
- Claude Opus 4.5: planner_toolcall_failure, empty EvidenceBus
- Claude Opus 4.6: planner_toolcall_failure, empty EvidenceBus
- Claude Opus 4.7: planner_toolcall_failure, empty EvidenceBus
- Claude Opus 4.8: planner_toolcall_failure, empty EvidenceBus
- Claude Sonnet 4.6: planner_toolcall_failure, empty EvidenceBus
- Deepseek V3.1: provider_error
- DeepSeek V4 Flash: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- DeepSeek V4 Pro: planner_toolcall_failure, empty EvidenceBus
- Llama 3.1 70b: provider_error
- Llama 3.1 8B Instruct: planner_toolcall_failure, empty EvidenceBus
- Llama 3.2 1b: provider_error
- Llama 3.2 1B Instruct: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Llama 3.2 3b: provider_error
- Llama 3.2 3B Instruct: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Llama 3.3 70B Instruct: planner_toolcall_failure, empty EvidenceBus
- Mistral Nemo Instruct 2407: planner_toolcall_failure, empty EvidenceBus
- Gemma 3 4B (Pretrained): planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Gemma 4 31B It: provider_error
- Gemma 4 E2B IT: planner_toolcall_failure, empty EvidenceBus
- Gemma 4 E4B It: provider_error
- MiniMax M2.7: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Kimi K2.6: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- GLM 5.1: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- MiMo V2.5 Pro: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- GPT-OSS 120B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- GPT-OSS 20B: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- Gemini 3.5 Flash: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- GPT-5.1: provider_error
- GPT-5.4: planner_toolcall_failure, empty EvidenceBus
- GPT-5.4 mini: planner_toolcall_failure, empty EvidenceBus
- GPT-5.4 nano: planner_toolcall_failure, empty EvidenceBus
- GPT-5.5: provider_error
- GPT-5 mini: planner_toolcall_failure, empty EvidenceBus
- GPT-5 nano: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus
- LFM2 24B A2B: planner_toolcall_failure, empty EvidenceBus
- SmolLM3 3B Base: planner_malformed_output, planner_toolcall_failure, empty EvidenceBus

## Objective Totals

- Models attempted: 53
- Models available: 42
- Models smoke-passed: 0
- Models benchmarked: 0
- Unsupported claims: 0
- no_tool_fp: 0

## Correctness Standard

Answer grounding correctness means semantic correctness, required information present, no false or unsupported claims, and correct scope/caveats. Hidden-eval or gold-wording similarity is not treated as real correctness in this report.

## Recommendation

- Safe to keep: True
- Safe to commit reports: True
- Safe to promote V2: False
- Reason: V2 remains explicit/shadow-only; promotion requires an explicit passing promotion gate and manual review.
