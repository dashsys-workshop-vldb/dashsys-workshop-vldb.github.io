# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 10 | 0.7067 | 0.93 | 0.8919 | 0.4109 | 0 |
| `guided_weak_llm` | 10 | 0.1458 | 0.09 | 0.3283 | 0.334 | 0 |
| `raw_weak_llm` | 10 | 0.076 | 0.0 | 0.3227 | 0.2692 | 0 |
| `weak_scaffold_api_recovery_v1` | 10 | 0.2509 | 0.09 | 0.8517 | 0.2716 | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 10 | 0.2456 | 0.18 | 0.8517 | 0.2017 | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 10 | 0.0973 | 0.18 | 0.0 | 0.1423 | 0 |
| `weak_scaffold_sql_retrieval_v1` | 10 | 0.097 | 0.18 | 0.0 | 0.1423 | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 10 | 0.0974 | 0.18 | 0.0 | 0.1423 | 0 |

- Small-model lift score: `0.1749`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
