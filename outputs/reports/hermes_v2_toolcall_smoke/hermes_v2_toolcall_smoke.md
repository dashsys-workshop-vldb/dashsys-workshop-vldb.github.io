# Hermes V2 Toolcall Smoke

- ok: `False`
- skipped: `False`
- skip_reason: ``
- strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- provider: `openai`
- model: `[REDACTED]/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit`
- sdk_path_used: `True`
- toolcall_supported: `True`
- prompt_timeout_sec: `180`
- llm_call_timeout_sec: `180`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 11.575 | 7.619 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 5.99 | 5.436 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 0 | False | None | 12.349 | 9.522 | 2.194 | EVIDENCE_LOCAL | False |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 13.848 | 10.881 | 2.329 | EVIDENCE_SQL | False |
| birthday_message_published | 1 | 0 | True | False | 0 | False | None | 37.454 | 33.103 | 3.355 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 1 | 0 | True | False | 3 | False | None | 40.046 | 33.578 | 3.717 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 1 | 1 | True | False | 0 | False | None | 82.986 | 36.52 | 3.407 | EVIDENCE_LIVE_IF_AVAILABLE | False |
