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
- partial_report: `True`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 12.728 | 9.377 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 9.119 | 8.558 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 0 | 0 | True | False | 0 | False | None | 54.767 | 23.006 | 2.685 | EVIDENCE_LOCAL | False |
| local_schema_count | 0 | 0 | True | False | 0 | False | None | 70.711 | 26.102 | 17.361 | EVIDENCE_SQL | False |
