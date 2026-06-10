# Weak Harness Engineering Eval

Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_full`
- Best variant: `weak_harness_answer_and_efficiency_v2`
- Best strict/API/SQL/answer: `0.2981` / `0.6241` / `0.12` / `0.2194`
- SQL improved over previous weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `False`
- Unsupported claims zero: `True`
- Recommendation: `weak_harness_balanced_improved_keep_shadow`

| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_answer_and_efficiency_v2` | 35 | 0.2981 | 0.12 | 0.6241 | 0.2194 | 1.0 | None | 0.9429 | 0 |
