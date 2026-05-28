# SQL_FIRST_API_VERIFY LLM Answer Verifier Organizer 35

| Strategy | Final | Correctness | SQL | API | Answer | Avg tool calls | Total SQL calls | Total API calls | Runtime total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6580 | 0.6850 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 15 | 36 | 22.7545 |
| `SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER` | 0.6554 | 0.6850 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 15 | 36 | 49.7750 |

## Deltas

- Final score delta: `-0.0026`
- Answer score delta: `0.0`
- SQL/API score deltas: `0.0` / `0.0`
- SQL/API call deltas: `0` / `0`
- Helped/hurt/neutral: `3/32/0`
- Severe regressions (delta <= -0.05): `0`
- Selected answer source counts: `{'LEGACY_SAFE_RENDERER': 35}`
- LLM answer counts: `{'attempted': 35, 'backend_used': 35, 'skipped': 0, 'fallback_true': 35, 'fallback_false': 0, 'rewrite_attempted': 0, 'rewrite_success': 0, 'generator_error_categories': {'empty_llm_answer': 35}}`

No promotion judgment was run.
