# Weak Harness Engineering Eval

Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_10`
- Best variant: `weak_harness_full_v1`
- Best strict/API/SQL/answer: `0.2597` / `0.8517` / `0.18` / `0.2361`
- SQL improved over previous weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Recommendation: `weak_harness_sql_improved_keep_shadow`

| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_balanced_sql_api_answer_v1` | 10 | 0.259 | 0.18 | 0.8517 | 0.2361 | 1.0 | None | 0.9 | 0 |
| `weak_harness_full_v1` | 10 | 0.2597 | 0.18 | 0.8517 | 0.2361 | 1.0 | None | 0.9 | 0 |
| `weak_harness_repair_loop_v1` | 10 | 0.247 | 0.18 | 0.8517 | 0.2079 | 1.0 | None | 1.0 | 0 |
| `weak_harness_schema_retrieval_v1` | 10 | 0.2457 | 0.18 | 0.8517 | 0.2079 | 1.0 | None | 1.0 | 0 |
| `weak_harness_slots_only_v1` | 10 | 0.0212 | 0.0 | 0.0 | 0.0737 | None | None | None | 0 |
| `weak_harness_unit_tested_sql_v1` | 10 | 0.2474 | 0.18 | 0.8517 | 0.2079 | 1.0 | None | 1.0 | 0 |
