# V2 Non-GPT Planner Compatibility Debug

Status: diagnostic_only. No full benchmark, promotion gate, or packaged-default change was run or made.

## Root Cause
- Pioneer provider is intentionally no-tool in this repo; non-GPT models returned no OpenAI-style tool_calls.
- The prior planner treated missing structured tool output plus weak JSON content as planner failure without a planner-owned repair attempt.
- The focused sweep fast-failed when all semantic JSON probes parsed badly, even though the conservative fallback route was EVIDENCE_PIPELINE.
- Mistral smoke also hit a report helper bug: list-shaped unsupported_claims caused _find_unsupported_counts to raise UnboundLocalError.

## Files Changed
- `dashagent/llm_unified_planner.py`
- `dashagent/pioneer_model_sweep.py`
- `dashagent/executor.py`
- `tests/test_v2_structured_tool_output.py`
- `tests/test_pioneer_model_sweep.py`

## Implementation
- `provider_capabilities`: Added PlannerProviderCapabilities; pioneer_chat uses supports_tool_calls=false, supports_json_content_fallback=true, requires_json_prompting=true.
- `planner_json_fallback`: Pioneer planner calls now request content JSON instead of tool calls; generic SDK providers still prefer tool calls.
- `repair_once`: Malformed planner JSON triggers one LLM-owned JSON repair attempt, then fails closed to EVIDENCE_PIPELINE with no backend-created passes.
- `timeout_trace`: Planner diagnostics include latency, timeout flag, toolcall attempted/supported, JSON fallback used, parse error, repair attempted, and success.
- `sweep_compatibility`: All semantic-probe parse failures no longer skip the smoke when they fail closed to EVIDENCE_PIPELINE.
- `report_bug_fix`: Unsupported-claim counter now handles list values without raising.

## Toolcall / JSON Probe
| Model | Model ID | Tool calls | JSON content pattern |
|---|---|---:|---|
| Qwen3 4B Instruct 2507 | `Qwen/Qwen3-4B-Instruct-2507` | 0 | empty |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 0 | ```json {   "route": "LLM_DIRECT",   "requires_evidence": false,   "reason": "Straightforward defini |
| Mistral Nemo Instruct 2407 | `mistralai/Mistral-Nemo-Instruct-2407` | 0 | {"route":"LLM_DIRECT|EVIDENCE_PIPELINE","requires_evidence":true,"reason":"A schema is a structure o |

## Historical Artifact Inspection
| Model safe name | Available | Key prior failure | JSON failures | Timeout/error |
|---|---:|---|---:|---|
| `claude_haiku_4_5` | True | _ProbeTimeout: focused smoke timed out after 60s | 0 | _ProbeTimeout: focused smoke timed out after 60s |
| `deepseek_v4_flash` | True | semantic_json_probe_parse_error | 7 |  |
| `qwen3_4b_instruct_2507` | True | semantic_json_probe_parse_error | 7 |  |
| `llama_3_1_8b_instruct` | True | _ProbeTimeout: focused smoke timed out after 60s | 0 | _ProbeTimeout: focused smoke timed out after 60s |
| `mistral_nemo_instruct_2407` | True | UnboundLocalError: cannot access local variable 'counts' where it is not associated with a value | 0 |  |

## Focused Smoke Results
| Model | Pass | Planner usable | Declared passes | SQL calls | API calls | EvidenceBus non-empty | no_tool_fp | Unsupported | Remaining failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Mistral Nemo Instruct 2407 | False | 3 | 3 | 2 | 1 | 3 | 2 | 0 | unsafe direct route for data/mixed prompts remains |
| Qwen3 4B Instruct 2507 | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | planner JSON still unusable / no LLM-owned passes |
| Claude Haiku 4.5 | False | None | None | 0 | 0 | None | None | None | bounded smoke timeout |

## Mistral Row-Level Smoke
| Prompt | Pass | SQL | API | Bypass | EvidenceBus | Declared passes | Semantic gate failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pure_concept_schema` | True | 0 | 0 | True | False | 0 | 0 |
| `pure_meta_list_schemas` | True | 0 | 0 | True | False | 0 | 0 |
| `mixed_inactive_journeys` | False | 0 | 0 | True | False | 0 | 0 |
| `ambiguous_user_schemas` | False | 0 | 0 | True | False | 0 | 0 |
| `local_schema_count` | True | 1 | 0 | False | True | 1 | 0 |
| `birthday_message_published` | True | 1 | 0 | False | True | 1 | 1 |
| `compare_local_live_birthday_status` | True | 0 | 1 | False | True | 1 | 1 |

## Validation
- `focused_tests`: python3 -m pytest -q tests/test_v2_structured_tool_output.py tests/test_pioneer_model_sweep.py -> 25 passed
- `full_pytest`: python3 -m pytest -q -> 1005 passed, 1 skipped
- `check_submission_ready`: ok=true; default_strategy_is_sql_first_api_verify=true; query_output_count=73; secret_scan ok=true
- `sdk_usage_audit`: runtime_llm_direct_http_hits=0
- `git_diff_check`: passed

## Decision
- Safe to keep: `True`
- Safe to commit: `True`
- Safe to run full benchmark next: `False`
- Reason: At least one non-GPT model now reaches evidence execution, but no representative model fully passes focused smoke; Mistral still has no-tool false positives, Qwen has zero usable passes, and Claude times out.

## Remaining Failures
- Mistral reaches evidence execution but still incorrectly bypasses evidence on mixed/data-like prompts, so focused smoke does not pass.
- Qwen fails closed into EVIDENCE_PIPELINE but produces no usable planner passes; all final gates fail because evidence is empty.
- Claude Haiku supports JSON content in the cheap probe but the full focused smoke still times out under the bounded wrapper.
- Full non-GPT benchmark should remain blocked until at least one non-GPT model passes focused smoke with no no-tool false positives.
