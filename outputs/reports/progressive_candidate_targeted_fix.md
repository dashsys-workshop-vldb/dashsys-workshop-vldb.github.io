# Progressive Candidate Targeted Fix
Generated: 2026-05-28T00:53:50.282368+00:00
## Implemented Fixes
- Restored same-evidence legacy answer selection inside full candidate and SAFE_API_PROBE.
- Added query-specific SAFE_API_PROBE template params.
- Fixed aggregate count propagation and local/live count wording.
- Tightened no-tool false-positive guards and local snapshot API skip.
- Added preverified answer short-circuit to avoid discarded LLM answer calls.
- Added a default post-SQL LLM backend-unavailable circuit breaker so unavailable backend retries are not repeated per API step.

## Organizer 35 Strict
| metric | SQL_FIRST | candidate | delta |
| --- | --- | --- | --- |
| final | 0.6581 | 0.6583 | 0.0002 |
| answer | 0.3207 | 0.3207 | 0.0 |
| API | 0.9791 | 0.9791 | 0.0 |
| SQL | 0.9333 | 0.9333 | 0.0 |
| tool calls | 1.4571 | 1.4571 | 0.0 |
| runtime | 0.6095 | 0.5288 | -0.0807 |
| execution time | 0.58 | 0.4314 | -0.1486 |
| tokens | 791.0571 | 809.3429 | 18.2858 |

- Severe regressions: `0`
- API_REQUIRED underuse: `0`
- Helped/hurt/neutral: `0/0/35`

## Internal 50 Focused Subset
| metric | baseline | candidate | delta |
| --- | --- | --- | --- |
| behavior | 0.7708 | 0.8354 | 0.0646 |
| final answer | 0.605 | 0.6425 | 0.0375 |
| overall | 0.6486 | 0.7618 | 0.1132 |
| SQL calls | 30 | 26 | -4 |
| API calls | 39 | 28 | -11 |
| runtime ms | - | - | 109.8593 |
| tokens | - | - | -172.32 |

- Helped/hurt/neutral: `12/0/38`
- No-tool false positives: `0`
- API_REQUIRED underuse: `0`
- Unsupported claims: `0`

## Smoke Results
| query_id | tool_calls | sql | api | entry_action | final_answer |
| --- | --- | --- | --- | --- | --- |
| fix4_concept_list_reasons | 0 | 0 | 0 | LLM_DIRECT | A schema is a blueprint for how data is structured: it defines fields, types, and constraints so systems can interpret records consistently. |
| fix4_meta_list_schemas | 0 | 0 | 0 | LLM_DIRECT | In that phrase, list means to return or enumerate matching items; this is a wording question, not a request to query schema records. |
| fix4_inactive_journeys | 2 | 1 | 1 | EVIDENCE_PIPELINE | There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API v |
| fix4_local_schema_count | 1 | 1 | 0 | EVIDENCE_PIPELINE | Local snapshot count: 74. |
| fix4_live_schema_count | 2 | 1 | 1 | EVIDENCE_PIPELINE | Local snapshot count: 74. API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials  |

## Validation
- focused_pytest: `85 passed in 2.76s`
- check_submission_ready: `ok=true; query_output_count=73; default_strategy=SQL_FIRST_API_VERIFY; all_query_outputs_use_expected_packaged_strategy=true`
- hidden_style: `48/48 cases; command exited 0`
- git_diff_check: `passed; command exited 0`
- targeted_secret_scan: `passed; filename-only scan found no hits in changed source/tests/reports/eval outputs`

Packaged default and final submission format are unchanged. No promotion judgment was run.
