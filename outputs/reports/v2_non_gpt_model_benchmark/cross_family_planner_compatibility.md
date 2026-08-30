# Cross-Family Planner Compatibility

Status: diagnostic_only. No V2 promotion, no packaged-default change, and no backend semantic planning were used.

## What Changed

- Pioneer/no-tool planner path uses content JSON fallback instead of requiring SDK tool calls.
- Planner JSON parser extracts JSON from code fences and surrounding text, then repairs once.
- Weak-model planner payload uses shorter schema/API context and four compact examples.
- Planner prompt now explicitly requires EVIDENCE_PIPELINE to include at least one pass and mixed prompts to include concept plus evidence passes.
- Pioneer/no-tool final answer composer uses JSON content instead of submit_final_answer tool calls.

## Representative Focused Smoke

| Family | Model | Model ID | Available | Smoke Pass | Planner Usable | Passes | SQL | API | Bypass | EvidenceBus | JSON Failures | no_tool_fp | Unsupported | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| claude | Claude Haiku 4.5 | claude-haiku-4-5 | True | False | 4 | 5 | 5 | 0 | 0 | 7 | 0 | 0 | 0 |  |
| deepseek | DeepSeek V4 Flash | deepseek-ai/DeepSeek-V4-Flash | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | latest rerun timeout 120s; no usable planner passes |
| glm | GLM 5.1 | zai-org/GLM-5.1 | True | False | 0 | 0 | 0 | 0 | 2 | 5 | 7 | 0 | 0 | no usable planner passes |
| gemma | Gemma 4 E4B It | google/gemma-4-E4B-it | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | timeout |
| llama | Llama 3.1 8B Instruct | meta-llama/Llama-3.1-8B-Instruct | True | False | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | no usable planner passes |
| mistral | Mistral Nemo Instruct 2407 | mistralai/Mistral-Nemo-Instruct-2407 | True | False | 3 | 3 | 3 | 0 | 2 | 5 | 0 | 0 | 0 |  |
| qwen | Qwen3 4B Instruct 2507 | Qwen/Qwen3-4B-Instruct-2507 | True | False | 0 | 0 | 0 | 0 | 0 | 7 | 7 | 0 | 0 | no usable planner passes |

## Full Benchmark Decision

Passing families: none.
Full benchmark run: False.
Reason: Fewer than 3 model families passed the focused smoke.

## Safety

no_tool_fp total: 0
unsupported_claims total: 0

## Observations

- Mistral is the strongest current representative: pure concept/meta bypass works and simple data prompts produce SQL passes, but mixed and compare prompts still miss evidence passes.
- Claude is callable and produces evidence for several data prompts, but it fails pure concept/meta bypass expectations and has final semantic gate failures.
- Qwen and GLM fail closed through JSON parse fallback for planner probes; they do not incorrectly bypass data prompts.
- Llama is callable but returns no usable planner passes in the focused smoke.
- Gemma E4B timed out during availability and was not evaluated further.
- DeepSeek V4 Flash timed out in the latest bounded rerun; existing artifact shows it is callable but fails closed with JSON parse failures.
