# SQL_FIRST LLM Answer Selection Fix

1. Root cause: non-empty LLM answers often omitted requested roles or introduced unsafe/low-quality wording; the selector needed high-precision gates rather than broad LLM preference.
2. LLM selected rows: `example_003`
3. Selected answer sources: `{'LEGACY_SAFE_RENDERER': 34, 'LLM_EVIDENCE_GROUNDED': 1}`
4. Organizer answer score: baseline `0.3207`, candidate `0.321`
5. SQL/API preserved: SQL `0.9333`, API `0.9791`, calls `15/36`
6. Helped/hurt/neutral: `1/0/34`
7. Unsupported claims: `0`
8. Empty-answer guard: focused strict scorer tests passed.
9. check_submission_ready: `ok=true`
10. hidden-style: `48 cases completed`
11. git diff --check: `ok=true`
12. Packaged default unchanged: `SQL_FIRST_API_VERIFY`

No promotion recommendation was made.
