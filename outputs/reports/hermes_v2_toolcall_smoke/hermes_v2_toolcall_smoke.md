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
- llm_call_timeout_sec: `180`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 16.801 | 16.454 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 9.643 | 9.41 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 32.336 | 12.38 | 9.867 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 29.456 | 26.291 | 2.82 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 22.967 | 18.644 | 3.603 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 0 | True | False | 2 | False | None | 46.676 | 21.808 | 10.093 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | False | None | 38.636 | 29.816 | 8.003 | EVIDENCE_LIVE_IF_AVAILABLE | True |
