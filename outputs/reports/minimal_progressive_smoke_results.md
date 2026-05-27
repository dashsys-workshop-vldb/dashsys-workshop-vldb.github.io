# Minimal Progressive Smoke Results

- Strategy: `ROBUST_GENERALIZED_HARNESS_CANDIDATE`
- Real AgentExecutor execution: `true`
- Synthetic trace: `false`
- Smoke rows: `6`
- No-tool false positives: `0`
- Unsupported claims: `0`
- API_REQUIRED underuse: `0`

## Rows

| Query | Kind | Entry | Route | SQL | API | Unsupported | Pass | Notes |
|---|---:|---|---|---:|---:|---:|---|---|
| `min_eval_concept_list_reasons` | conceptual_no_tool | `LLM_DIRECT` | `LLM_SAFE_DIRECT` | 0 | 0 | 0 | `True` | ok |
| `min_eval_meta_list_schemas` | meta_language_no_tool | `LLM_DIRECT` | `LLM_SAFE_DIRECT` | 0 | 0 | 0 | `True` | ok |
| `min_eval_current_schemas` | data_retrieval | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | `True` | ok |
| `min_eval_inactive_journeys` | status_lookup | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | `True` | ok |
| `min_eval_local_schema_count` | local_count | `EVIDENCE_PIPELINE` | `SQL_ONLY` | 1 | 1 | 0 | `True` | local count still made API call; safe but inefficient |
| `min_eval_live_schema_count` | live_count | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | `True` | ok |

## Key Observations
- Local-snapshot count stayed safe but still made one API call; this is an efficiency/tuning target, not an unsafe no-tool issue.
- Data/status/live prompts entered the evidence pipeline; no data-like smoke query took a pure no-tool path.
- Live/platform count preserved the API path and caveated when live verification could not be completed locally.
- Answer verifier fell back deterministically where caveat wording failed strict verification; unsupported claims stayed at 0 in these smokes.
