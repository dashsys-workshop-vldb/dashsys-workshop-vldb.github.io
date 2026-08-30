# Concise LLM Rewrite Smoke

| query_id | eligible | rewrite_category | selected_source | SQL | API | final answer |
|---|---:|---|---|---:|---:|---|
| `concise_rewrite_schema_count` | `True` | `backend_unavailable` | `LEGACY_SAFE_RENDERER` | 1 | 1 | You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable. |
| `concise_rewrite_birthday_published` | `False` | `not_attempted` | `LEGACY_SAFE_RENDERER` | 1 | 1 | The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable. |
| `concise_rewrite_inactive_journeys` | `False` | `not_attempted` | `LEGACY_SAFE_RENDERER` | 1 | 1 | There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable. |
| `concise_rewrite_concept_schema` | `False` | `not_attempted` | `LEGACY_SAFE_RENDERER` | 1 | 1 | Based on the evidence provided, matching datasets are: AJO Push Profile Dataset, AJO Interactive Messaging Profile Dataset, AJO Message Feedback Event Dataset, Journeys, AJO Email Tracking Experience Event Dataset, ODE DecisionEvents - external-benchmarking decisioning, hkg_adls_profile_count_history, weRetail: Customer Actions, AJO STO Summary Dataset, and AJO Entity Dataset. Live API verification was not executed because Adobe credentials are unavailable. |

Selected source counts: `{'LEGACY_SAFE_RENDERER': 4}`
Rewrite category counts: `{'backend_unavailable': 1, 'not_attempted': 3}`
