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
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 18.752 | 18.498 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 9.957 | 9.725 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 31.587 | 12.621 | 9.298 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 28.788 | 26.02 | 2.429 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 21.815 | 17.486 | 3.69 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 0 | True | False | 2 | False | None | 43.162 | 21.981 | 8.62 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 1 | 1 | True | False | 1 | False | None | 27.059 | 21.944 | 4.521 | EVIDENCE_LIVE_IF_AVAILABLE | True |
