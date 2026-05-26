# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 10 | 0.7052 | 0.93 | 0.8919 | 0.4109 | 0 |
| `guided_weak_llm` | 10 | 0.1458 | 0.09 | 0.3283 | 0.334 | 0 |
| `raw_weak_llm` | 10 | 0.076 | 0.0 | 0.3227 | 0.2692 | 0 |
| `weak_harness_balanced_sql_api_answer_v1` | 10 | 0.259 | 0.18 | 0.8517 | 0.2361 | 0 |
| `weak_harness_full_v1` | 10 | 0.2597 | 0.18 | 0.8517 | 0.2361 | 0 |
| `weak_harness_repair_loop_v1` | 10 | 0.247 | 0.18 | 0.8517 | 0.2079 | 0 |
| `weak_harness_schema_retrieval_v1` | 10 | 0.2457 | 0.18 | 0.8517 | 0.2079 | 0 |
| `weak_harness_slots_only_v1` | 10 | 0.0212 | 0.0 | 0.0 | 0.0737 | 0 |
| `weak_harness_unit_tested_sql_v1` | 10 | 0.2474 | 0.18 | 0.8517 | 0.2079 | 0 |

- Small-model lift score: `0.1837`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
