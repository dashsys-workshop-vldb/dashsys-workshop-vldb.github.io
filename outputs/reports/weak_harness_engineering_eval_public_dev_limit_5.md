# Weak Harness Engineering Eval

Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.

- Run label: `public_dev_limit_5`
- Best variant: `weak_harness_repair_loop_v1`
- Best strict/API/SQL/answer: `0.3768` / `0.9858` / `0.36` / `0.27`
- SQL improved over previous weak scaffold: `True`
- API non-regression: `True`
- Answer non-regression: `True`
- Unsupported claims zero: `True`
- Recommendation: `weak_harness_balanced_improved_keep_shadow`

| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_balanced_sql_api_answer_v1` | 5 | 0.3735 | 0.36 | 0.9858 | 0.2583 | 1.0 | None | 1.0 | 0 |
| `weak_harness_full_v1` | 5 | 0.3717 | 0.36 | 0.9858 | 0.2583 | 1.0 | None | 1.0 | 0 |
| `weak_harness_repair_loop_v1` | 5 | 0.3768 | 0.36 | 0.9858 | 0.27 | 1.0 | None | 1.0 | 0 |
| `weak_harness_schema_retrieval_v1` | 5 | 0.3741 | 0.36 | 0.9858 | 0.27 | 1.0 | None | 1.0 | 0 |
| `weak_harness_slots_only_v1` | 5 | 0.0211 | 0.0 | 0.0 | 0.0734 | None | None | None | 0 |
| `weak_harness_unit_tested_sql_v1` | 5 | 0.3768 | 0.36 | 0.9858 | 0.27 | 1.0 | None | 1.0 | 0 |
