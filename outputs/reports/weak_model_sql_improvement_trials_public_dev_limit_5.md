# Weak Model SQL Improvement Trials

Diagnostic-only SQL correctness trials for the weak-model scaffold. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_5`
- Best strict variant: `weak_scaffold_balanced_sql_api_v2`
- Best strict/API/SQL/answer: `0.3771` / `0.9858` / `0.36` / `0.2697`
- Best SQL variant: `weak_scaffold_answer_fallback_v3`
- Best SQL variant strict/API/SQL/answer: `0.3737` / `0.9858` / `0.36` / `0.258`
- SQL improved over current weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Bounded gate passed: `True`

| Mode | Rows | Strict | SQL | API | Answer | SQL unit pass | Repair success | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_scaffold_answer_fallback_v3` | 5 | 0.3737 | 0.36 | 0.9858 | 0.258 | 1.0 | None | 0 |
| `weak_scaffold_api_recovery_v1` | 5 | 0.297 | 0.18 | 0.9858 | 0.2381 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_answer_v3` | 5 | 0.3716 | 0.36 | 0.9858 | 0.258 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 5 | 0.3771 | 0.36 | 0.9858 | 0.2697 | 1.0 | None | 0 |
| `weak_scaffold_sql_lift_api_recovery_v3` | 5 | 0.3717 | 0.36 | 0.9858 | 0.258 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 5 | 0.186 | 0.36 | 0.0 | 0.1504 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_v1` | 5 | 0.1844 | 0.36 | 0.0 | 0.1504 | 1.0 | None | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 5 | 0.1864 | 0.36 | 0.0 | 0.1504 | 1.0 | None | 0 |
