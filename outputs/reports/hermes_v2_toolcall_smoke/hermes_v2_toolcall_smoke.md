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
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 18.81 | 18.578 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 10.07 | 9.865 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 30.724 | 12.68 | 8.769 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 26.308 | 23.737 | 2.301 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 20.772 | 16.298 | 3.889 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 0 | True | False | 2 | False | None | 41.966 | 20.455 | 8.907 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | False | None | 27.715 | 22.478 | 4.663 | EVIDENCE_LIVE_IF_AVAILABLE | True |
