# Progressive Answer Regression Audit

Generated: 2026-05-28T00:39:33.544422+00:00

## Current Organizer 35

| metric | SQL_FIRST | candidate | delta |
| --- | --- | --- | --- |
| final | 0.658 | 0.6555 | -0.0025 |
| answer | 0.3207 | 0.3207 | 0.0 |
| API | 0.9791 | 0.9791 | 0.0 |
| SQL | 0.9333 | 0.9333 | 0.0 |
| tool calls | 1.4571 | 1.4571 | 0.0 |
| runtime | 0.634 | 1.3462 | 0.7122 |
| answer time | 0.0111 | 0.0552 | 0.0441 |

- Severe regressions now: `0`
- API_REQUIRED underuse rows: `0`

Answer/API/SQL correctness now matches baseline. Remaining final-score gap is efficiency/runtime only.
