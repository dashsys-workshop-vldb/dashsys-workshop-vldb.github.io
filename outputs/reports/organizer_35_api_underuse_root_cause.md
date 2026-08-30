# Organizer 35 API Underuse Root Cause

Root cause: SQL direct-answer suppression was too broad for organizer-style strict API-sensitive rows.

| Query | Classification | API need | Baseline API | Combined API | Delta |
|---|---|---|---:|---:|---:|
| `example_001` | `sql_complete_but_api_gold_required, live_status_signal_missed` | `API_OPTIONAL` | 1 | 0 | -0.2597 |
| `example_002` | `sql_complete_but_api_gold_required` | `API_OPTIONAL` | 1 | 0 | -0.2124 |
| `example_005` | `sql_complete_but_api_gold_required, endpoint_family_required_missed` | `API_OPTIONAL` | 1 | 0 | -0.2101 |

## General Fix Direction

Preserve safe API calls when SQL looks complete but the runtime facts show API-required mode, explicit live/status/sandbox/API signal, or an API-sensitive endpoint family matching the prompt domain.

## Fix Verification

- General guard: strict API preservation for objective retrieval/status/live/API-family signals with safe matching API candidates.
- Prompt-id hardcoding used: `false`.
- Post-fix API_REQUIRED underuse: `0`.
- Post-fix API score baseline vs combined: `0.9791` / `0.9791`.
- Remaining blocker: combined_safe final score remains below baseline due runtime/overhead, not API underuse.
