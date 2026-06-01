# Pioneer Model Sweep Summary

Status: diagnostic_only. This sweep changes only the configured Pioneer LLM model for V2 semantic/concept paths.

## Default Model Set

- Qwen3 4B Instruct 2507: qwen_small_instruct
- Qwen3 8B: qwen
- Qwen3.5 9B: qwen
- Qwen3.6 27B: qwen
- Qwen3.6 Flash: qwen
- Qwen3.6 Plus: qwen
- Qwen3.6 35B A3B: qwen
- Qwen3.7 Max: qwen
- Claude Haiku 4.5: anthropic_fast_small
- DeepSeek V4 Flash: deepseek_cheap_fast
- DeepSeek V4 Pro: deepseek
- Llama 3.1 8B Instruct: llama_small_instruct
- Llama 3.2 3B Instruct: llama_small_instruct
- Mistral Nemo Instruct 2407: mistral_compact_instruct
- Gemma 4 E4B It: gemma_small_instruct
- Gemma 4 31B It: gemma
- MiniMax M2.7: minimax
- Kimi K2.6: kimi
- GLM 5.1: glm
- GPT-OSS 20B: gpt_oss
- GPT-OSS 120B: gpt_oss

## Results

| Model | Group | Available | Pass | JSON Failures | LLM Direct | Evidence Pipeline | Bypassed | EvidenceBus | no_tool_fp | Unsupported | Latency Sec |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| [REDACTED] | anthropic_fast_small | True | False | 0 | 2 | 5 | 2 | 5 | 0 | 0 | 98.5635 |
| DeepSeek V4 Flash | deepseek_cheap_fast | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9.11 |
| GLM 5.1 | glm | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6.1379 |
| [REDACTED] | llama_small_instruct | True | False | 0 | 4 | 3 | 4 | 3 | 2 | 0 | 56.8855 |
| [REDACTED] | mistral_compact_instruct | True | False | 0 | 3 | 4 | 3 | 4 | 1 | 0 | 102.8158 |
| [REDACTED] | qwen_small_instruct | True | False | 7 | 0 | 7 | 0 | 7 | 0 | 0 | 87.0569 |

## Summary Answers

1. Safest non-GPT model: none evaluated as safe.
2. Fewest JSON failures: GLM 5.1.
3. Incorrect EvidenceBus bypass models: ['[REDACTED]', '[REDACTED]'].
4. Viable cross-family small models: [].
5. Per-family safety is determined by focused smoke pass, no_tool_fp=0, and unsupported_claims=0.
6. GPT-4o necessary based on this focused run: True.
