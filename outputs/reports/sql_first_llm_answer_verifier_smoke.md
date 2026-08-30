# SQL_FIRST_API_VERIFY LLM Answer Verifier Smoke

| Query ID | SQL | API | Selected source | LLM attempted | Backend used | Fallback | Final answer |
|---|---:|---:|---|---|---|---|---|
| `sql_first_llm_answer_inactive_journeys` | 1 | 1 | `LEGACY_SAFE_RENDERER` | `True` | `True` | `True` | There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was n... |
| `sql_first_llm_answer_birthday_published` | 1 | 1 | `LEGACY_SAFE_RENDERER` | `True` | `True` | `True` | The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed ... |
| `sql_first_llm_answer_local_schema_count` | 1 | 1 | `DETERMINISTIC_FALLBACK` | `True` | `True` | `True` | Local snapshot count: 74. API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials are unavailable. |

Summary: `{'query_count': 3, 'total_sql_calls': 3, 'total_api_calls': 3, 'llm_attempted': 3, 'llm_backend_used': 3, 'fallback_used': 3, 'selected_source_counts': {'LEGACY_SAFE_RENDERER': 2, 'DETERMINISTIC_FALLBACK': 1}}`
