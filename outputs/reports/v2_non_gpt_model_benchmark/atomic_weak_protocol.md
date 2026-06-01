# Atomic Weak Protocol Report

Status: diagnostic_only. No V2 promotion. Packaged default remains `SQL_FIRST_API_VERIFY`.

## Implementation Summary

- Added `dashagent/v2_atomic_weak_protocol.py` with Atomic Evidence Need Checklist, fixed five task slots, per-slot SQL/API candidate parsing, candidate repair, and objective diagnostics.
- Wired `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` planner to the atomic protocol via `dashagent/llm_unified_planner.py`.
- Added `max_tokens=120` cap for per-pass DIRECT subtasks with compatibility fallback for older test clients.
- Added Pioneer sweep model-status and pass-success diagnostics.

## Ownership Boundary

- LLM owns evidence judgment, decomposition, path choice, SQL/API candidate generation, candidate repair, and final answer generation.
- Backend only parses fixed fields, mechanically aggregates checklist bits, validates shape/gates, schedules, executes, stores results, and verifies grounding.
- No backend semantic routing/planning was added; `backend_semantic_routing_used=false` is reported in planner diagnostics.

## Focused Smoke

Command: `python3 scripts/run_pioneer_model_sweep.py --models "Claude Haiku 4.5,Mistral Nemo Instruct 2407,Llama 3.1 8B Instruct,Qwen3 4B Instruct 2507,DeepSeek V4 Flash,GLM 5.1"`

Completion: `partial_current_run_interrupted_after_slow_model_hang`

| Model | Current Run Completed | Status | Pass | JSON Failures | no_tool_fp | Unsupported | LLM Direct | Evidence | Bypassed | EvidenceBus | Declared Passes | Failed Prompts |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Claude Haiku 4.5 | True | connected | False | 0 | 0 | 0 | 1 | 6 | 1 | 6 | 5 | pure_meta_list_schemas, ambiguous_user_schemas, local_schema_count, birthday_message_published, mixed_inactive_journeys, compare_local_live_birthday_status |
| Mistral Nemo Instruct 2407 | True | connected | False | 0 | 0 | 0 | 0 | 7 | 0 | 7 | 17 | pure_concept_schema, pure_meta_list_schemas, local_schema_count, birthday_message_published, mixed_inactive_journeys, compare_local_live_birthday_status |
| Llama 3.1 8B Instruct | True | connected | False | 0 | 1 | 0 | 2 | 5 | 2 | 5 | 4 | pure_meta_list_schemas, ambiguous_user_schemas, local_schema_count, birthday_message_published, mixed_inactive_journeys, compare_local_live_birthday_status |
| Qwen3 4B Instruct 2507 | True | connected | False | 7 | 0 | 0 | 0 | 7 | 0 | 7 | 0 | pure_concept_schema, pure_meta_list_schemas, ambiguous_user_schemas, local_schema_count, birthday_message_published, mixed_inactive_journeys, compare_local_live_birthday_status |
| DeepSeek V4 Flash | False | None | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - |
| GLM 5.1 | False | None | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - |

Full benchmark run: `False`. Reason: Not run because fewer than three current-run model families passed focused smoke.

## Validation

- Focused V2/planner/sweep tests: 125 passed.
- Full pytest: 1067 passed, 1 skipped in 60.69s.
- `python3 scripts/check_submission_ready.py`: ok=true, packaged default SQL_FIRST_API_VERIFY, query_output_count=73, secret scan ok.
- `python3 scripts/generate_sdk_usage_audit.py`: runtime_llm_direct_http_hits=0.
- `git diff --check`: passed.

## Known Blockers

- No current-run non-GPT model passed the focused smoke end-to-end.
- Qwen failed closed with JSON/atomic parse failures; safety held but usability failed.
- DeepSeek/GLM slow-model segment hung before current-run files were refreshed.
- Evidence-pass success counts remain low or zero in focused smoke outputs, so candidate-slot reliability still needs work.

## Promotion Decision

No promotion recommendation. Keep `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` shadow/research-only.
