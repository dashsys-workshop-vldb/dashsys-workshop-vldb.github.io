# Cross-Family Planner Compatibility Fix

Status: diagnostic_only. No V2 promotion and no packaged-default change.

## Root Causes Fixed

- Removed angle-bracket fake SQL placeholders from planner examples and made examples schema-aware when schema_context contains table names.
- Added shape-only PassGraphGate requirements for EVIDENCE_PIPELINE to declare at least one executable SQL/API evidence pass.
- Added one LLM-owned pass-graph repair attempt after PassGraphGate failure, with backend supplying only graph-shape error feedback.
- Added compact safe-GET endpoint context for weak-model planner payloads.
- Added planner JSON tolerance for code fences, surrounding text, and trailing commas without semantic plan creation.

## Focused Smoke Results

| Family | Model | Runner Completed | Smoke Pass | Planner Usable | Passes | SQL | API | EvidenceBus Non-empty | Syntax Gate Failures | Semantic Gate Failures | JSON Failures | no_tool_fp | Unsupported |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| claude | Claude Haiku 4.5 | True | False | 5 | 7 | 6 | 0 | 6 | 2 | 5 | 0 | 0 | 0 |
| deepseek | DeepSeek V4 Flash | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| glm | GLM 5.1 | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| llama | Llama 3.1 8B Instruct | True | False | 5 | 8 | 7 | 1 | 7 | 0 | 2 | 0 | 0 | 0 |
| mistral | Mistral Nemo Instruct 2407 | True | True | 5 | 7 | 4 | 2 | 5 | 0 | 2 | 0 | 0 | 0 |
| qwen | Qwen3 4B Instruct 2507 | True | False | 0 | 0 | 0 | 0 | 7 | 7 | 7 | 7 | 0 | 0 |

## Decision

Families passing focused smoke runner: mistral.
Families passing with zero final gate failures: none.
At least 3 families passed smoke: False.
Safe to run full benchmark next: False.

## Validation

- `python3 -m pytest -q`: 1024 passed, 1 skipped.
- `python3 scripts/check_submission_ready.py`: ok=true; default strategy remains SQL_FIRST_API_VERIFY; query output count=73; secret scan ok=true.
- `python3 scripts/generate_sdk_usage_audit.py`: runtime_llm_direct_http_hits=0.
- `git diff --check`: passed.

## Remaining Blockers

- Only Mistral passed the seven-prompt focused smoke runner; target of at least 3 families was not met.
- Claude and Llama still route pure concept/meta prompts through evidence instead of LLM_DIRECT.
- Qwen still fails closed with JSON parse/semantic fallback and no executable passes.
- DeepSeek and GLM timed out under the bounded one-model smoke wrapper.
- Several callable models still have final semantic gate failures even when prompt-level route/evidence checks pass.
