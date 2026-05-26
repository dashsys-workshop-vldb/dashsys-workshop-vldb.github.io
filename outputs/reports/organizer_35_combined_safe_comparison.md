# Organizer 35 Combined Safe Comparison

Strict organizer-style evaluator over `data/data.json`.

| Strategy | Final | Correctness | SQL | API | Answer | Tools | API calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6581 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 36 | 0.5986 | 799.4286 |
| STAGED_EVIDENCE_APPLIED_TRIAL | 0.6394 | 0.6641 | 0.9333 | 0.8823 | 0.3369 | 1.3429 | 32 | 0.4345 | 775.3143 |
| POST_SQL_DETERMINISTIC_APPLIED_TRIAL | 0.6393 | 0.6641 | 0.9333 | 0.8823 | 0.3369 | 1.3429 | 32 | 0.4577 | 775.3714 |
| COMBINED_SAFE_APPLIED_TRIAL | 0.6392 | 0.6641 | 0.9333 | 0.8823 | 0.3369 | 1.3429 | 32 | 0.4891 | 775.4857 |

- API calls saved by combined_safe vs baseline: `4`
- API calls added by combined_safe vs baseline: `0`
- Final answers changed: `4`
- API-required underuse: `3`
- Unsupported claims: `0`
