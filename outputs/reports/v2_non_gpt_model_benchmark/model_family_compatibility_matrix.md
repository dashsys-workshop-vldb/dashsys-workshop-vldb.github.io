# Pioneer Model Family Compatibility Matrix

Status: diagnostic_only. This matrix groups existing focused-smoke and probe artifacts by model family.

| Family | Available | Representative | Toolcalls | JSON fallback | Planner usable | Passes | SQL | API | EvidenceBus non-empty | no_tool_fp | Unsupported | Timeouts | Malformed |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen | 12 | Qwen3 1.7B Base | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 |
| mistral | 1 | Mistral Nemo Instruct 2407 | False | True | 3 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 |
| llama | 4 | Llama 3.1 8B Instruct | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| claude | 7 | Claude Haiku 4.5 | False | True | 4 | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| deepseek | 2 | DeepSeek V4 Flash | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| gemma | 2 | Gemma 3 4B (Pretrained) | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| glm | 1 | GLM 5.1 | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| kimi | 1 | Kimi K2.6 | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| minimax | 1 | MiniMax M2.7 | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| gpt_oss | 2 | GPT-OSS 120B | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| other | 8 | Gemini 3.5 Flash | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 21 |
