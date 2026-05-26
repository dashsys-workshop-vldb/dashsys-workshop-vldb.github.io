# Weak Model SQL Improvement Trials

Diagnostic-only SQL correctness trials for the weak-model scaffold. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_10`
- Best strict variant: `weak_scaffold_api_recovery_v1`
- Best strict/API/SQL/answer: `0.2509` / `0.8517` / `0.09` / `0.2716`
- Best SQL variant: `weak_scaffold_balanced_sql_api_v2`
- Best SQL variant strict/API/SQL/answer: `0.2456` / `0.8517` / `0.18` / `0.2017`
- SQL improved over current weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Bounded gate passed: `True`

| Mode | Rows | Strict | SQL | API | Answer | SQL unit pass | Repair success | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_scaffold_api_recovery_v1` | 10 | 0.2509 | 0.09 | 0.8517 | 0.2716 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 10 | 0.2456 | 0.18 | 0.8517 | 0.2017 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 10 | 0.0973 | 0.18 | 0.0 | 0.1423 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_v1` | 10 | 0.097 | 0.18 | 0.0 | 0.1423 | 1.0 | None | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 10 | 0.0974 | 0.18 | 0.0 | 0.1423 | 1.0 | None | 0 |
