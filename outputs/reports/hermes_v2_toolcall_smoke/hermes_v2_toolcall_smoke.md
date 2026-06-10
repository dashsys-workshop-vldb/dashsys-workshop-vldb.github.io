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
- effective_llm_call_timeout_sec: `110`
- partial_report: `False`

## Rows

| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |
|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|
| pure_concept_schema | 0 | 0 | True | False | 0 | False | None | 30.668 | 28.589 | 0.0 | DIRECT | True |
| pure_meta_list_schemas | 0 | 0 | True | False | 0 | False | None | 67.429 | 37.169 | 3.815 | DIRECT | False |
| ambiguous_user_schemas | 0 | 0 | True | False | 0 | False | None | 90.413 | 39.543 | 3.211 | EVIDENCE_LOCAL | False |
| local_schema_count | 0 | 0 | None | None | 0 | True | checkpoint_llm_final_answer_composer_start | 120.004 | 0.0 | 0.0 | EVIDENCE_SQL | False |
| birthday_message_published | 0 | 0 | None | None | 0 | True | checkpoint_llm_unified_planner_start | 120.006 | 0.0 | 0.0 | EVIDENCE_LOCAL | False |
| mixed_inactive_journeys | 0 | 0 | None | None | 0 | True | checkpoint_llm_owned_pass_graph_repair_start | 120.003 | 0.0 | 0.0 | EVIDENCE_LOCAL | False |
| compare_local_live_birthday_status | 0 | 0 | None | None | 0 | True | checkpoint_llm_owned_pass_graph_repair_start | 120.004 | 0.0 | 0.0 | EVIDENCE_LIVE_IF_AVAILABLE | False |
