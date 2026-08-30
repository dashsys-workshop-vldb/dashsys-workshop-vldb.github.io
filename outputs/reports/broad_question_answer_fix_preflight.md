# Broad Question Answer Fix Preflight

- Generated at: `2026-05-28T14:44:07.730087+00:00`
- Packaged default strategy: `SQL_FIRST_API_VERIFY`
- Packaged default unchanged: `True`
- `SQL_FIRST_API_VERIFY_HYBRID_ANSWER` available: `True`
- Preflight check_submission_ready ok: `True`
- Git status: `?? "outputs/source_code/scripts/run_dev_eval 2.py"
?? "outputs/source_code/scripts/run_live_api_readiness_smoke 2.py"`

## Latest Hybrid Organizer35

| Metric | Value |
|---|---:|
| `avg_answer_score` | 0.293 |
| `avg_answer_time` | 0.0184 |
| `avg_api_score` | 0.9791 |
| `avg_correctness_score` | 0.6752 |
| `avg_estimated_tokens` | 777.8571 |
| `avg_execution_time` | 0.7833 |
| `avg_final_score` | 0.6477 |
| `avg_metadata_tokens` | 823.5429 |
| `avg_planning_time` | 0.0017 |
| `avg_preprocessing_time` | 0.0029 |
| `avg_prompt_tokens` | 1465.6286 |
| `avg_runtime` | 0.8337 |
| `avg_sql_score` | 0.9333 |
| `avg_tool_call_count` | 1.4571 |

## Current Known Root Causes

| Root cause | Count |
|---|---:|
| `CANONICAL_RENDERER_WRONG_TEMPLATE` | 10 |
| `FUZZY_SIMILARITY_DROP` | 8 |
| `TEMPLATE_TOO_SHORT` | 8 |
| `WRONG_OBJECT_LABEL` | 4 |
| `MISSING_EXACT_NUMBER` | 3 |
| `ANSWER_INTENT_WRONG` | 2 |
| `OVER_CAVEATED` | 2 |
| `ANSWER_MODE_WRONG` | 1 |
| `HYBRID_LOST_SUBSTRING_MATCH` | 1 |
| `MISSING_STATUS_WORD` | 1 |
| `UNDER_CAVEATED` | 1 |

- Runtime gold use: `false`; gold remains post-execution audit-only.
