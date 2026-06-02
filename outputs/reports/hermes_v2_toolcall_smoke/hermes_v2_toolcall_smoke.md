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
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 63.897 | 63.382 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 27.056 | 26.722 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 1 | 0 | True | False | 3 | False | None | 53.694 | 28.369 | 24.785 | EVIDENCE_LOCAL | True |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 33.867 | 27.356 | 6.099 | EVIDENCE_SQL | True |
| birthday_message_published | 1 | 0 | True | False | 1 | False | None | 43.134 | 34.703 | 7.602 | EVIDENCE_LOCAL | True |
| mixed_inactive_journeys | 1 | 0 | True | False | 2 | False | None | 91.506 | 70.643 | 8.694 | EVIDENCE_LOCAL | True |
| compare_local_live_birthday_status | 0 | 0 | None | None | 0 | True | checkpoint_llm_unified_planner_start | 120.002 | 0.0 | 0.0 | EVIDENCE_LIVE_IF_AVAILABLE | False |
