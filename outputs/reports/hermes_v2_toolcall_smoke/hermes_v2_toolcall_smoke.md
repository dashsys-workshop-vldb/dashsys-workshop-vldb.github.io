# Hermes V2 Toolcall Smoke

- ok: `False`
- skipped: `False`
- skip_reason: ``
- strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- provider: `openai`
- model: `[REDACTED]/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit`
- sdk_path_used: `True`
- toolcall_supported: `True`
- prompt_timeout_sec: `120`
- llm_call_timeout_sec: `180`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 8.825 | 8.272 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 6.125 | 5.579 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 0 | 1 | True | False | 0 | False | None | 15.21 | 9.514 | 2.468 | EVIDENCE_LOCAL | False |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 14.465 | 11.413 | 2.411 | EVIDENCE_SQL | False |
| birthday_message_published | 0 | 0 | True | False | 0 | False | None | 72.433 | 34.947 | 2.007 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 0 | 0 | True | False | 0 | False | None | 72.086 | 34.831 | 2.136 | EVIDENCE_LOCAL | False |
| compare_local_live_birthday_status | 1 | 1 | True | False | 0 | False | None | 50.593 | 39.988 | 4.461 | EVIDENCE_LIVE_IF_AVAILABLE | False |
