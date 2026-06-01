# Cross-Family Planner Compatibility Final Fix

## Executive Summary

Implemented the compatibility fixes requested for Pioneer/non-GPT weak-model planning: two-phase LLM-owned RouteGate plus Evidence Planner, weak-model JSON schema simplification with allowed-value arrays, separated route/evidence examples, optional LLM-owned plan self-check, split initial/final answer-gate metrics, and slow-model route probes.

Focused smoke result: **0 / 6 models passed**. The acceptance target of at least 3 passing families was **not met**, so the full benchmark was **not run**.

The route boundary improved for pure concept/meta prompts on: Claude Haiku 4.5, Mistral Nemo Instruct 2407, DeepSeek V4 Flash.

The remaining failures are mostly evidence-plan quality and final answer semantic-gate failures, not backend SQL/API deterministic planning gaps. Under the current design rule, the backend should not take semantic ownership by choosing tables, columns, endpoints, or rewrites.

## Files Changed

- `dashagent/llm_unified_planner.py`
- `dashagent/pioneer_model_sweep.py`
- `dashagent/llm_final_answer_composer.py`
- `tests/test_v2_structured_tool_output.py`
- `tests/test_pioneer_model_sweep.py`
- `tests/test_llm_final_answer_composer.py`

## Implemented Changes

- Added two-phase Pioneer/non-GPT planning: RouteGate first, Evidence Planner only for `EVIDENCE_PIPELINE`.
- Malformed RouteGate output is repaired once, then fails closed to `EVIDENCE_PIPELINE` and calls the Evidence Planner.
- Replaced pipe-delimited enum strings in weak-model planner payloads with explicit `*_allowed_values` arrays.
- Split route examples from evidence examples. Route examples contain no SQL/API/schema context; evidence examples use schema-context-aware columns.
- Added optional LLM-owned plan self-check/revision before `PassGraphGate`.
- Split answer-gate metrics into initial/final syntax/semantic failures and repaired-success counts.
- Added short RouteGate probes for slow models before expensive full focused smoke runs.

## Focused Smoke Summary

| Model | Available | Smoke Pass | Planner Usable | Declared Passes | LLM Direct | Evidence Pipeline | Bypassed | EBus Non-Empty | JSON Failures | Final Syntax Fail | Final Semantic Fail | Repairs | Repaired Success | Unsupported | No-Tool FP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | True | False | 5 | 8 | 2 | 5 | 2 | 5 | 0 | 1 | 4 | 4 | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | True | False | 5 | 5 | 2 | 5 | 2 | 5 | 0 | 0 | 4 | 4 | 0 | 0 | 0 |
| Llama 3.1 8B Instruct | True | False | 5 | 14 | 0 | 7 | 0 | 7 | 0 | 0 | 6 | 6 | 0 | 0 | 0 |
| Qwen3 4B Instruct 2507 | True | False | 0 | 0 | 0 | 7 | 0 | 7 | 7 | 7 | 7 | 7 | 0 | 0 | 0 |
| DeepSeek V4 Flash | True | False | 3 | 3 | 2 | 5 | 2 | 5 | 1 | 0 | 2 | 3 | 1 | 0 | 0 |
| GLM 5.1 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## RouteGate / Self-Check Diagnostics

| Model | Route Counts | Self-Check Counts | Evidence Planner Counts |
|---|---|---|---|
| Claude Haiku 4.5 | `{"EVIDENCE_PIPELINE": 5, "LLM_DIRECT": 2, "llm_route_gate_used": 7, "route_gate_success": 7}` | `{"self_check_not_revised": 5, "self_check_parse_errors": 5, "self_check_used": 5}` | `{"evidence_pipeline_prompts": 5, "evidence_planner_called": 5, "evidence_planner_skipped": 2}` |
| Mistral Nemo Instruct 2407 | `{"EVIDENCE_PIPELINE": 4, "LLM_DIRECT": 2, "llm_route_gate_used": 6, "route_gate_success": 6}` | `{}` | `{"evidence_pipeline_prompts": 5, "evidence_planner_called": 4, "evidence_planner_skipped": 2}` |
| Llama 3.1 8B Instruct | `{}` | `{}` | `{"evidence_pipeline_prompts": 7}` |
| Qwen3 4B Instruct 2507 | `{}` | `{}` | `{"evidence_pipeline_prompts": 7}` |
| DeepSeek V4 Flash | `{"EVIDENCE_PIPELINE": 1, "llm_route_gate_used": 1, "route_gate_success": 1}` | `{}` | `{"evidence_pipeline_prompts": 5, "evidence_planner_called": 1}` |
| GLM 5.1 | `{}` | `{}` | `{}` |

## Per-Prompt Smoke Rows

| Model | Prompt | Pass | SQL | API | Bypass | EvidenceBus | RouteGate Route | Evidence Planner | Final Syntax Fail | Final Semantic Fail | Unsupported |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Claude Haiku 4.5 | pure_concept_schema | True | 0 | 0 | True | False | LLM_DIRECT | False | 0 | 0 | 0 |
| Claude Haiku 4.5 | pure_meta_list_schemas | True | 0 | 0 | True | False | LLM_DIRECT | False | 0 | 0 | 0 |
| Claude Haiku 4.5 | ambiguous_user_schemas | False | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 1 | 1 | 0 |
| Claude Haiku 4.5 | local_schema_count | True | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 0 | 0 |
| Claude Haiku 4.5 | birthday_message_published | False | 1 | 1 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Claude Haiku 4.5 | mixed_inactive_journeys | False | 1 | 1 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Claude Haiku 4.5 | compare_local_live_birthday_status | False | 1 | 1 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Mistral Nemo Instruct 2407 | pure_concept_schema | True | 0 | 0 | True | False | LLM_DIRECT | False | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | pure_meta_list_schemas | True | 0 | 0 | True | False | LLM_DIRECT | False | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | ambiguous_user_schemas | False | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Mistral Nemo Instruct 2407 | local_schema_count | True | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 0 | 0 |
| Mistral Nemo Instruct 2407 | birthday_message_published | False | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Mistral Nemo Instruct 2407 | mixed_inactive_journeys | False | 1 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 1 | 0 |
| Mistral Nemo Instruct 2407 | compare_local_live_birthday_status | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | pure_concept_schema | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | pure_meta_list_schemas | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | ambiguous_user_schemas | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | local_schema_count | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | birthday_message_published | True | 1 | 0 | False | True |  |  | 0 | 0 | 0 |
| Llama 3.1 8B Instruct | mixed_inactive_journeys | False | 1 | 0 | False | True |  |  | 0 | 1 | 0 |
| Llama 3.1 8B Instruct | compare_local_live_birthday_status | False | 1 | 1 | False | True |  |  | 0 | 1 | 0 |
| Qwen3 4B Instruct 2507 | pure_concept_schema | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | pure_meta_list_schemas | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | ambiguous_user_schemas | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | local_schema_count | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | birthday_message_published | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | mixed_inactive_journeys | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| Qwen3 4B Instruct 2507 | compare_local_live_birthday_status | False | 0 | 0 | False | True |  |  | 1 | 1 | 0 |
| DeepSeek V4 Flash | pure_concept_schema | True | 0 | 0 | True | False |  |  | 0 | 0 | 0 |
| DeepSeek V4 Flash | pure_meta_list_schemas | True | 0 | 0 | True | False |  |  | 0 | 0 | 0 |
| DeepSeek V4 Flash | ambiguous_user_schemas | True | 0 | 1 | False | True |  |  | 0 | 0 | 0 |
| DeepSeek V4 Flash | local_schema_count | True | 1 | 0 | False | True |  |  | 0 | 0 | 0 |
| DeepSeek V4 Flash | birthday_message_published | False | 0 | 1 | False | True |  |  | 0 | 1 | 0 |
| DeepSeek V4 Flash | mixed_inactive_journeys | False | 0 | 0 | False | True |  |  | 0 | 1 | 0 |
| DeepSeek V4 Flash | compare_local_live_birthday_status | False | 0 | 0 | False | True | EVIDENCE_PIPELINE | True | 0 | 0 | 0 |

## Acceptance Decision

- At least 3 families passed focused smoke: **False**.
- Full benchmark run: **No**.
- Reason: full benchmark was intentionally skipped because the focused-smoke acceptance target was not met.
- Packaged default: unchanged by this patch.
- V2 promotion recommendation: **No promotion recommendation**.

## Remaining Blockers

- No model passed the full seven-prompt focused smoke under final answer-gate criteria.
- Claude, Mistral, and DeepSeek now handle pure concept/meta via RouteGate bypass, but fail evidence/date/mixed/compare prompts at final semantic answer gate.
- Llama still sends pure concept/meta prompts through evidence instead of direct bypass in the latest smoke.
- Qwen still produces malformed planner JSON and fails closed to evidence pipeline with zero usable declared passes.
- GLM route probe remained unusable and skipped full smoke.
- Remaining failures are LLM evidence-plan/SQL/API/final-answer quality issues; backend must not deterministic-plan or rewrite them under the current design rule.

## Validation

| Command | Result |
|---|---|
| `python3 -m pytest -q` | exit 0; 1036 passed, 1 skipped |
| `python3 scripts/check_submission_ready.py` | exit 0; ok=true; default_strategy_is_sql_first_api_verify=true; query_output_count=73; secret_scan.ok=true |
| `python3 scripts/generate_sdk_usage_audit.py` | exit 0; runtime_llm_direct_http_hits=0 |
| `git diff --check` | exit 0; no whitespace errors |

No credential or environment values are included in this report.
