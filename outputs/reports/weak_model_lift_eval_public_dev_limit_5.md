# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 5 | 0.7022 | 0.9 | 1.0 | 0.3781 | 0 |
| `guided_weak_llm` | 5 | 0.1603 | 0.18 | 0.1492 | 0.3288 | 0 |
| `raw_weak_llm` | 5 | 0.04 | 0.0 | 0.1879 | 0.2411 | 0 |
| `weak_harness_balanced_sql_api_answer_v1` | 5 | 0.3735 | 0.36 | 0.9858 | 0.2583 | 0 |
| `weak_harness_full_v1` | 5 | 0.3717 | 0.36 | 0.9858 | 0.2583 | 0 |
| `weak_harness_repair_loop_v1` | 5 | 0.3768 | 0.36 | 0.9858 | 0.27 | 0 |
| `weak_harness_schema_retrieval_v1` | 5 | 0.3741 | 0.36 | 0.9858 | 0.27 | 0 |
| `weak_harness_slots_only_v1` | 5 | 0.0211 | 0.0 | 0.0 | 0.0734 | 0 |
| `weak_harness_unit_tested_sql_v1` | 5 | 0.3768 | 0.36 | 0.9858 | 0.27 | 0 |

- Small-model lift score: `0.3368`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
