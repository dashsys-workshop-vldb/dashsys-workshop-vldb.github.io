# Pioneer Model Sweep Summary

Status: diagnostic_only. This sweep changes only the configured Pioneer LLM model for V2 semantic/concept paths.

## Default Model Set

- Gpt 4o: gpt_baseline
- Claude Haiku 4.5: anthropic_fast_small
- DeepSeek V4 Flash: deepseek_cheap_fast
- Qwen3 4B Instruct 2507: qwen_small_instruct
- Llama 3.1 8B Instruct: llama_small_instruct
- Mistral Nemo Instruct 2407: mistral_compact_instruct
- Gemma 4 E4B It: gemma_small_instruct

## Results

| Model | Group | Available | Pass | JSON Failures | LLM Direct | Evidence Pipeline | Bypassed | EvidenceBus | no_tool_fp | Unsupported | Latency Sec |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Gpt 4o | gpt_baseline | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1.3844 |
| Claude Haiku 4.5 | anthropic_fast_small | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.0544 |
| DeepSeek V4 Flash | deepseek_cheap_fast | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.7228 |
| Qwen3 4B Instruct 2507 | qwen_small_instruct | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.2281 |
| Llama 3.1 8B Instruct | llama_small_instruct | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1.38 |
| Mistral Nemo Instruct 2407 | mistral_compact_instruct | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.8203 |
| Gemma 4 E4B It | gemma_small_instruct | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.2446 |

## Summary Answers

1. Safest non-GPT model: none evaluated as safe.
2. Fewest JSON failures: none available.
3. Incorrect EvidenceBus bypass models: [].
4. Viable cross-family small models: [].
5. Per-family safety is determined by focused smoke pass, no_tool_fp=0, and unsupported_claims=0.
6. GPT-4o necessary based on this focused run: None.
