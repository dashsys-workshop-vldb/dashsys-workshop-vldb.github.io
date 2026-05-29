# Pioneer Model Full Benchmark Summary

## Purpose

This benchmark verifies cross-model stability of the V2 system, not model selection or optimization.

## Model-Major Semantics

Each callable model runs the complete benchmark suite before the runner switches to the next model. No per-prompt model rotation is used.

## Model Availability

| Display Name | Model ID | Available | Error |
| --- | --- | ---: | --- |
| Gpt 4o | `gpt-4o` | False | auth_or_401 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | True |  |
| DeepSeek V4 Flash | `deepseek-ai/DeepSeek-V4-Flash` | True |  |
| Qwen3 4B Instruct 2507 | `Qwen/Qwen3-4B-Instruct-2507` | True |  |
| Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | True |  |
| Mistral Nemo Instruct 2407 | `mistralai/Mistral-Nemo-Instruct-2407` | True |  |
| Gemma 4 E4B It | `google/gemma-4-E4B-it` | True |  |

## Per-Model Benchmark Scores

| Model | Verdict | Org35 Final | Org35 Correctness | Org35 Answer | Org35 SQL | Org35 API | Org35 Tool Calls | Internal50 Combined | Internal50 Behavior |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Gpt 4o | UNAVAILABLE |  |  |  |  |  |  |  |  |
| Claude Haiku 4.5 | STABLE | 0.6353 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |
| DeepSeek V4 Flash | SAFE_BUT_DEGRADED | 0.6308 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |
| Qwen3 4B Instruct 2507 | SAFE_BUT_DEGRADED | 0.6354 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |
| Llama 3.1 8B Instruct | STABLE | 0.6352 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |
| Mistral Nemo Instruct 2407 | STABLE | 0.6286 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |
| Gemma 4 E4B It | STABLE | 0.6293 | 0.6606 | 0.2918 | 0.9333 | 0.9591 | 1.4000 | 0.7816 | 0.8546 |

## Safety

| Model | no_tool_fp | api_required_underuse | unsupported_claims | concrete_data_llm_direct | JSON failures | Semantic fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gpt 4o | None | None | None | None | None | None |
| Claude Haiku 4.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| DeepSeek V4 Flash | 0 | 0 | 0 | 0 | 5 | 5 |
| Qwen3 4B Instruct 2507 | 0 | 0 | 0 | 0 | 6 | 6 |
| Llama 3.1 8B Instruct | 0 | 0 | 0 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemma 4 E4B It | 0 | 0 | 0 | 0 | 0 | 0 |

## Routing / Evidence

| Model | LLM_DIRECT | LLM_SAFE_DIRECT | Evidence Pipeline | Bypassed | EvidenceBus Built | Post-Evidence Router |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gpt 4o | None | None | None | None | None | None |
| Claude Haiku 4.5 | 2 | 0 | 4 | 2 | 4 | 4 |
| DeepSeek V4 Flash | 2 | 0 | 4 | 2 | 4 | 4 |
| Qwen3 4B Instruct 2507 | 2 | 0 | 4 | 2 | 4 | 4 |
| Llama 3.1 8B Instruct | 2 | 0 | 4 | 2 | 4 | 4 |
| Mistral Nemo Instruct 2407 | 2 | 0 | 4 | 2 | 4 | 4 |
| Gemma 4 E4B It | 2 | 0 | 4 | 2 | 4 | 4 |

## Cross-Model Conclusion

- Callable models: 6
- Completed full benchmark models: Claude Haiku 4.5, DeepSeek V4 Flash, Qwen3 4B Instruct 2507, Llama 3.1 8B Instruct, Mistral Nemo Instruct 2407, Gemma 4 E4B It
- Unavailable models: Gpt 4o
- Unsafe models: none
- V2 stable across callable models: True
- Weak malformed responses failed closed: True

No recommendation is made to continue with only the best model; this report is about system robustness across model families.
