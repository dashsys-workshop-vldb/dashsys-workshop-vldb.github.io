# Weak Model SQL Improvement Trials

Diagnostic-only SQL correctness trials for the weak-model scaffold. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_full`
- Best strict variant: `weak_scaffold_api_recovery_v1`
- Best strict/API/SQL/answer: `0.2871` / `0.6241` / `0.06` / `0.2261`
- Best SQL variant: `weak_scaffold_balanced_sql_api_v2`
- Best SQL variant strict/API/SQL/answer: `0.2739` / `0.6241` / `0.12` / `0.2103`
- SQL improved over current weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Bounded gate passed: `False`

| Mode | Rows | Strict | SQL | API | Answer | SQL unit pass | Repair success | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_scaffold_api_recovery_v1` | 35 | 0.2871 | 0.06 | 0.6241 | 0.2261 | 1.0 | None | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 35 | 0.2739 | 0.12 | 0.6241 | 0.2103 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 35 | 0.1187 | 0.12 | 0.1717 | 0.134 | 1.0 | None | 0 |
| `weak_scaffold_sql_retrieval_v1` | 35 | 0.1183 | 0.12 | 0.1717 | 0.134 | 1.0 | None | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 35 | 0.1188 | 0.12 | 0.1717 | 0.134 | 1.0 | None | 0 |
