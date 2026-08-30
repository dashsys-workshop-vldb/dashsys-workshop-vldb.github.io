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
| Qwen3.6 35B A3B | qwen | True | False | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 15.9316 |

## Summary Answers

1. Safest non-GPT model: none evaluated as safe.
2. Fewest JSON failures: Qwen3.6 35B A3B.
3. Incorrect EvidenceBus bypass models: [].
4. Viable cross-family small models: [].
5. Per-family safety is determined by focused smoke pass, no_tool_fp=0, and unsupported_claims=0.
6. GPT-4o necessary based on this focused run: True.
