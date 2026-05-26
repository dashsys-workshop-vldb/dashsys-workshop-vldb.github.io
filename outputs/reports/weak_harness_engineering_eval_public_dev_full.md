# Weak Harness Engineering Eval

Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_full`
- Best variant: `weak_harness_full_v1`
- Best strict/API/SQL/answer: `0.2732` / `0.6241` / `0.12` / `0.2188`
- SQL improved over previous weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `False`
- Unsupported claims zero: `True`
- Recommendation: `weak_harness_answer_regression`

| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_full_v1` | 35 | 0.2732 | 0.12 | 0.6241 | 0.2188 | 1.0 | None | 0.9429 | 0 |
