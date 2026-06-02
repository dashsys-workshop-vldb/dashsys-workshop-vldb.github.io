# Hermes V2 Toolcall Smoke

- ok: `True`
- skipped: `False`
- skip_reason: ``
- strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- provider: `openai`
- model: `[REDACTED]/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit`
- sdk_path_used: `True`
- toolcall_supported: `True`
- prompt_timeout_sec: `120`
- llm_call_timeout_sec: `60`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 13.196 | 12.912 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 10.828 | 10.507 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 32.513 | 15.174 | 16.937 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 34.102 | 29.213 | 4.481 | EVIDENCE_SQL | True |
| birthday_message_published | 2 | 0 | True | False | 2 | False | None | 33.263 | 24.513 | 8.067 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 1 | True | False | 2 | False | None | 41.886 | 25.598 | 12.361 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | False | None | 35.476 | 25.242 | 9.555 | EVIDENCE_LIVE_IF_AVAILABLE | True |
