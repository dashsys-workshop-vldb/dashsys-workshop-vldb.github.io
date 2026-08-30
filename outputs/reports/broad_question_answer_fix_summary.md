# Broad Question Answer Fix Summary

- Generated at: `2026-05-28T15:13:51.828993+00:00`

## Implementation

- BroadQuestionClassifier implemented: `true`
- AnswerIntentRouter uses broad conceptual/data/mixed routing.
- Structured data selection is legacy-first with selective hybrid override.
- Mixed composer remains concept plus structured data, verifier-bounded.

## Organizer35

| Metric | SQL_FIRST_API_VERIFY | SQL_FIRST_API_VERIFY_HYBRID_ANSWER | Delta |
|---|---:|---:|---:|
| Final | 0.6513 | 0.6518 | 0.0005 |
| Answer | 0.3207 | 0.3207 | 0.0 |
| SQL | 0.9333 | 0.9333 | 0.0 |
| API | 0.9791 | 0.9791 | 0.0 |
| Tool calls | 1.4571 | 1.4571 | 0.0 |
| Runtime | 2.9681 | 2.4977 | -0.4704 |
| Tokens | 791.3429 | 791.3714 | 0.0285 |

- Selected source counts: `{'LEGACY_SAFE_RENDERER': 35}`
- Broad question type counts: `{'DATA_BROAD': 19, 'NOT_BROAD': 16}`
- Helped/hurt/neutral rows: `{'neutral': 35}`
- Unsupported claims: `0`

## Smoke

| Query | Broad type | Intent | Mode | Source | SQL/API | Final answer |
|---|---|---|---|---|---:|---|
| `broad_fix_concept_schema` | `CONCEPTUAL_BROAD` | `CONCEPT` | `LLM_CONCEPT` | `HYBRID_LLM_CONCEPT` | 1/1 | A schema defines the structure, fields, and expected shape of data. |
| `broad_fix_data_schema_count` | `DATA_BROAD` | `COUNT` | `LEGACY_FIRST_DATA` | `LEGACY_SAFE_RENDERER` | 1/1 | You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable. |
| `broad_fix_recent_dataset_changes` | `DATA_BROAD` | `LIST` | `LEGACY_FIRST_DATA` | `LEGACY_SAFE_RENDERER` | 1/1 | The most recent dataset changes occurred on 2026-04-14 21:08:54.000 UTC, including hkg_adls_segment_profile_history (2026-04-14 21:08:54.000 UTC), hkg_adls_profile_cou... |
| `broad_fix_mixed_inactive_journeys` | `MIXED_BROAD` | `MIXED` | `HYBRID_MIXED` | `HYBRID_MIXED` | 1/1 | An inactive journey is a journey that is not currently active or running. Journeys: Birthday Message (updated); Gold Tier Welcome Email (created). API unavailable/erro... |

## Validation

- Focused tests: `87 passed`
- check_submission_ready: `passed`
- git diff --check: `passed`
- hidden-style: `None` cases, all passed `True`
- Packaged default unchanged: `True`

## Remaining Blockers

- Organizer35 answer score is now equal to baseline, not higher; current selection is intentionally conservative and selects legacy-safe renderer for all organizer rows.
- Broad conceptual smoke still uses the SQL_FIRST tool path because routing/planning changes were explicitly out of scope for this answer-layer pass; answer text is corrected conceptually after evidence is collected.

- Promotion recommendation: `none`
