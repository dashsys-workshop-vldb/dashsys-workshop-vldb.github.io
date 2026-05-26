# Weak Model SQL Improvement Trials

Diagnostic-only SQL correctness trials for the weak-model scaffold. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_10`
- Best strict variant: `weak_scaffold_answer_fallback_v3`
- Best strict/API/SQL/answer: `0.2605` / `0.8517` / `0.18` / `0.2359`
- Best SQL variant: `weak_scaffold_answer_fallback_v3`
- Best SQL variant strict/API/SQL/answer: `0.2605` / `0.8517` / `0.18` / `0.2359`
- SQL improved over current weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Bounded gate passed: `True`

| Mode | Rows | Strict | SQL | API | Answer | SQL unit pass | Repair success | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_scaffold_answer_fallback_v3` | 10 | 0.2605 | 0.18 | 0.8517 | 0.2359 | 1.0 | None | 0 |
| `weak_scaffold_api_recovery_v1` | 10 | 0.2492 | 0.09 | 0.8517 | 0.2712 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_answer_v3` | 10 | 0.2598 | 0.18 | 0.8517 | 0.2359 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 10 | 0.2474 | 0.18 | 0.8517 | 0.2077 | 1.0 | None | 0 |
| `weak_scaffold_sql_lift_api_recovery_v3` | 10 | 0.2582 | 0.18 | 0.8517 | 0.2359 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 10 | 0.1015 | 0.18 | 0.0 | 0.1556 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_v1` | 10 | 0.1015 | 0.18 | 0.0 | 0.1556 | 1.0 | None | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 10 | 0.1017 | 0.18 | 0.0 | 0.1556 | 1.0 | None | 0 |
