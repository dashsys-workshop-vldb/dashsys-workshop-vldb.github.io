# Weak Harness Engineering Eval

Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_10`
- Best variant: `weak_harness_answer_and_efficiency_v2`
- Best strict/API/SQL/answer: `0.2758` / `0.8517` / `0.18` / `0.2367`
- SQL improved over previous weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Recommendation: `weak_harness_sql_improved_keep_shadow`

| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_answer_and_efficiency_v2` | 10 | 0.2758 | 0.18 | 0.8517 | 0.2367 | 1.0 | None | 0.9 | 0 |
