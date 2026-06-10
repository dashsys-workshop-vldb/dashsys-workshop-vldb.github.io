# Weak-Model Stable Protocol Report

## Summary

- Implemented a universal V2 weak-model protocol with Route Card, Task Ledger Card, per-task Pass Candidate Cards, one repair attempt, and plain-text final answers.
- Packaged default remains `SQL_FIRST_API_VERIFY`.
- Backend ownership remains mechanical: parsing, graph/gate checks, scheduling, cache, execution, EvidenceBus/ResultBundle, and final grounding gates only.
- Latest focused smoke did **not** meet the acceptance target; no full benchmark was run.

## Files Changed

- `dashagent/v2_weak_model_protocol.py`
- `dashagent/llm_unified_planner.py`
- `dashagent/executor.py`
- `dashagent/llm_final_answer_composer.py`
- `dashagent/pioneer_model_sweep.py`
- `tests/test_v2_weak_model_protocol.py`
- `tests/test_v2_structured_tool_output.py`

## Focused Smoke Results

| Model | Available | Rerun status | Prompt pass | Smoke pass | Route cards | Task ledgers | Candidates | SQL | API | Evidence non-empty | Final semantic failures | Unsupported | no_tool_fp |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | True | completed_after_route_prompt_tightening | 6/7 | False | 7 | 5 | 7 | 3 | 4 | 5 | 1 | 0 | 0 |
| Mistral Nemo Instruct 2407 | True | completed_after_route_prompt_tightening | 4/7 | False | 7 | 3 | 2 | 1 | 0 | 4 | 1 | 0 | 1 |
| Llama 3.1 8B Instruct | True | completed_after_route_prompt_tightening | 2/7 | False | 7 | 2 | 4 | 2 | 2 | 3 | 2 | 0 | 2 |
| Qwen3 4B Instruct 2507 | True | completed_after_route_prompt_tightening | 0/7 | False | 0 | 0 | 0 | 0 | 0 | 7 | 7 | 0 | 0 |
| DeepSeek V4 Flash | True | bounded_retry_timed_out_before_fresh_report; retained last completed guarded-probe result | 0/0 | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GLM 5.1 | True | bounded_retry_timed_out_before_fresh_report; retained last completed guarded-probe result | 0/0 | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Acceptance target met: `False`. Families passed: `[]`.

## Validation

- `python3 -m pytest -q`: 1045 passed, 1 skipped.
- `python3 scripts/check_submission_ready.py`: ok=true, default strategy still SQL_FIRST_API_VERIFY, query_output_count=73, secret_scan.ok=true.
- `python3 scripts/generate_sdk_usage_audit.py`: runtime_llm_direct_http_hits=0.
- `git diff --check`: passed.

## Remaining Blockers

- Latest effective focused smoke did not reach the 3-family pass target.
- Claude completed 6/7 prompts but failed one final semantic gate after route prompt tightening.
- Mistral and Llama still produced concrete-data LLM_DIRECT bypasses on some prompts.
- Qwen failed route/task/final-answer protocol handling and ended with final answer gate failures on all prompts.
- DeepSeek and GLM bounded current rerun attempts timed out before fresh per-model reports; prior guarded-probe results remained unavailable/unusable.
- Several SQL compile gate failures are correctly caught and repaired/fallbacked, but they still block full focused-smoke pass criteria.

## Decision

Keep V2 shadow-only. Do not run full benchmark and do not promote until at least 3 model families pass focused smoke.
