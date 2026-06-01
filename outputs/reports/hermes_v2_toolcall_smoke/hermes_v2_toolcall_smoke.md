# Hermes V2 Toolcall Smoke

- ok: `False`
- skipped: `False`
- skip_reason: ``
- strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- provider: `openai`
- model: `[REDACTED]/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit`
- sdk_path_used: `True`
- toolcall_supported: `True`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Compiled SQL | Compiled API | Runtime Facts | Local Facts | Caveats/Errors | Initial Gate Fail | Final Gate Fail | Expected | Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 1 | True | False | 1 | 1 | 3 | 3 | 1 | 1 | 1 | EVIDENCE_LOCAL | False |
| local_schema_count | 1 | 0 | True | False | 1 | 0 | 3 | 3 | 0 | 1 | 1 | EVIDENCE_SQL | False |
| birthday_message_published | 1 | 1 | True | False | 1 | 1 | 1 | 1 | 1 | 1 | 1 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 1 | 1 | True | False | 1 | 1 | 2 | 2 | 1 | 1 | 1 | EVIDENCE_LOCAL | False |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | 1 | 1 | 1 | 1 | 0 | 0 | EVIDENCE_LIVE_IF_AVAILABLE | True |
