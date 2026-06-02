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
- llm_call_timeout_sec: `60`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 11.71 | 11.42 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 7.957 | 7.728 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 45.152 | 12.12 | 32.673 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 27.209 | 20.715 | 6.202 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 61.127 | 18.965 | 10.129 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 1 | 1 | True | False | 2 | False | None | 90.915 | 20.92 | 27.179 | EVIDENCE_LOCAL | False |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | False | None | 46.361 | 24.829 | 20.822 | EVIDENCE_LIVE_IF_AVAILABLE | True |
