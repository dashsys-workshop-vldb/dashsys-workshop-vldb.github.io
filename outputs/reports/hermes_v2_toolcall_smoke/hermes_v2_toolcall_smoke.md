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
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 9.253 | 8.047 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 6.738 | 5.688 | 0.0 | DIRECT | True |
| ambiguous_user_schemas | 0 | 0 | True | False | 0 | False | None | 49.192 | 48.09 | 0.0 | EVIDENCE_LOCAL | False |
| local_schema_count | 1 | 0 | True | False | 1 | False | None | 28.975 | 23.309 | 4.205 | EVIDENCE_SQL | False |
| birthday_message_published | 0 | 0 | None | None | 0 | True | checkpoint_llm_owned_pass_graph_gate | 180.005 | 0.0 | 0.0 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 0 | 0 | None | None | 0 | True | checkpoint_llm_unified_planner_start | 180.015 | 0.0 | 0.0 | EVIDENCE_LOCAL | False |
| compare_local_live_birthday_status | 1 | 1 | True | False | 0 | False | None | 139.171 | 62.888 | 5.595 | EVIDENCE_LIVE_IF_AVAILABLE | False |
