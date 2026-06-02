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
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 6.987 | 6.498 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 5.739 | 5.374 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 29.886 | 10.101 | 8.079 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 13.056 | 10.088 | 2.417 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 19.503 | 12.58 | 2.876 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 0 | True | False | 2 | False | None | 21.437 | 12.499 | 5.842 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 2 | 2 | True | False | 1 | False | None | 36.677 | 28.84 | 6.974 | EVIDENCE_LIVE_IF_AVAILABLE | True |
