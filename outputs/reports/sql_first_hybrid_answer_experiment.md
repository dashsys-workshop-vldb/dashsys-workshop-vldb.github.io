# SQL First Hybrid Answer Experiment

Implemented: yes
Packaged default unchanged: yes, `SQL_FIRST_API_VERIFY` remains default.
Tool path unchanged: True

## Organizer35

| Strategy | Final | SQL | API | Answer | Tool calls |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6564 | 0.9333 | 0.9791 | 0.3207 | 1.4571 |
| SQL_FIRST_API_VERIFY_HYBRID_ANSWER | 0.6477 | 0.9333 | 0.9791 | 0.293 | 1.4571 |

SQL/API score deltas: `0.0` / `0.0`
Answer score delta: `-0.0277`
Final score delta: `-0.0087`
SQL/API/tool call deltas zero: `True`
Selected answer sources: `{'LEGACY_SAFE_RENDERER': 24, 'DETERMINISTIC_FALLBACK': 9, 'HYBRID_CANONICAL_CAVEAT': 1, 'HYBRID_CANONICAL_DATA': 1}`
Fallback counts: `{'true': 33, 'false': 2}`
Unsupported claim count: `0`

Focused tests: 57 passed.
check_submission_ready: passed.
git diff --check: passed.

Known blocker: answer score did not improve; the hybrid layer is currently a safe explicit experiment, not a promotion candidate.

No promotion recommendation.


## Audits

- Unsafe runtime hardcode count: 0
- Unsafe fake-score count: 0
- Runtime visible evaluator-data count: 0
- SDK direct LLM HTTP hits: 0
