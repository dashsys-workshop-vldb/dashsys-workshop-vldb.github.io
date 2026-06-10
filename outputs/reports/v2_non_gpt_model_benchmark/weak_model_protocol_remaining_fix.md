# Weak Model Protocol Remaining Fix

Status: diagnostic_only. No promotion recommendation. Packaged default remains `SQL_FIRST_API_VERIFY`.

## Implemented

- Added tolerant mechanical parsing in `dashagent/v2_weak_model_protocol.py` for Route Card, Task Ledger, Direct Route Challenge, and SQL/API Candidate cards.
- Added LLM-owned Direct Route Challenge for proposed `DIRECT` route decisions. Malformed challenge output repairs once, then fails closed to evidence.
- Added bounded weak-protocol LLM call token limits: route 80, direct challenge 40, task ledger 300, candidate 220, candidate repair 220.
- Added SQL/API candidate repair prompts that include the gate error plus compact schema/API context. Backend still does not repair or rewrite SQL/API.
- Added final-answer task and pass-result checklist fields, required caveats, repair context details, and final-answer max token limit 500.
- Split Pioneer smoke evidence metrics into built, runtime facts, runtime non-empty, error/caveat-only, and successful pass counts.
- Preserved public Pioneer model labels in reports while keeping secret redaction.

## Focused Smoke

Command:

```bash
python3 scripts/run_pioneer_model_sweep.py --models "Claude Haiku 4.5,Mistral Nemo Instruct 2407,Llama 3.1 8B Instruct,Qwen3 4B Instruct 2507,DeepSeek V4 Flash,GLM 5.1"
```

The first run completed and wrote the standard Pioneer sweep reports. After adding report-only metric fields, the same focused smoke was rerun; per-model outputs were written, but the process did not exit after the artifacts appeared, so it was terminated and the summary was regenerated from the per-model JSON files without additional model calls.

| Model | Callable | Focused Smoke Pass | no_tool_fp | unsupported_claims | JSON Failures | LLM Direct | Evidence Pipeline | Runtime Facts | Caveat/Error Only | Failed Prompts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Claude Haiku 4.5 | true | false | 0 | 0 | 0 | 2 | 5 | 0 | 4 | mixed_inactive_journeys |
| Mistral Nemo Instruct 2407 | true | false | 1 | 0 | 0 | 3 | 4 | 1 | 3 | birthday_message_published; mixed_inactive_journeys |
| Llama 3.1 8B Instruct | true | false | 2 | 0 | 0 | 4 | 3 | 4 | 1 | ambiguous_user_schemas; local_schema_count; birthday_message_published; mixed_inactive_journeys; compare_local_live_birthday_status |
| Qwen3 4B Instruct 2507 | true | false | 0 | 0 | 7 | 0 | 7 | 0 | 7 | all 7 focused prompts |
| DeepSeek V4 Flash | true | false | 0 | 0 | 0 | 0 | 0 | 0 | 0 | route probe failed; full smoke skipped |
| GLM 5.1 | true | false | 0 | 0 | 0 | 0 | 0 | 0 | 0 | route probe failed; full smoke skipped |

Direct Route Challenge results:

- Claude: pure concept and pure meta prompts challenged; both returned `NEEDS_EVIDENCE=NO`.
- Mistral: pure concept, pure meta, and mixed inactive journey prompts challenged; all returned `NEEDS_EVIDENCE=NO`, so the mixed prompt remained a no-tool false positive.
- Llama: pure concept, pure meta, ambiguous schemas, and mixed inactive journey prompts challenged; all returned `NEEDS_EVIDENCE=NO`, so ambiguous/mixed data-like prompts remained no-tool false positives.
- Qwen: malformed route outputs failed closed to evidence for all prompts.
- DeepSeek/GLM: short route probe failed, so full focused smoke was skipped.

Result: the remaining fix improves parser tolerance and observability, but the acceptance target of at least 3 passing non-GPT families was not met. No full benchmark was run.

## Validation

```bash
python3 -m pytest -q
# 1056 passed, 1 skipped in 61.14s

python3 scripts/check_submission_ready.py
# ok=true; default_strategy_is_sql_first_api_verify=true; query_output_count=73; secret_scan.ok=true

python3 scripts/generate_sdk_usage_audit.py
# runtime_llm_direct_http_hits=0

git diff --check
# passed with no output
```

## Notes

- Backend still does not decompose prompts, choose SQL/API paths, generate SQL/API, rewrite SQL/API, or optimize hidden/gold wording.
- LLM still owns route, task ledger, candidate SQL/API generation, repair, and final aggregation.
- The strict Direct Route Challenge is LLM-owned. The backend only applies `NEEDS_EVIDENCE=YES|NO` and fails closed to evidence on malformed output.
- No credentials or environment values are included in this report.
