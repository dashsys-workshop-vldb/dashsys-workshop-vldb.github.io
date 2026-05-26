# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 5 | 0.7024 | 0.9 | 1.0 | 0.3781 | 0 |
| `guided_weak_llm` | 5 | 0.1603 | 0.18 | 0.1492 | 0.3288 | 0 |
| `raw_weak_llm` | 5 | 0.04 | 0.0 | 0.1879 | 0.2411 | 0 |
| `weak_scaffold_api_recovery_v1` | 5 | 0.3044 | 0.18 | 0.9858 | 0.2379 | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 5 | 0.374 | 0.36 | 0.9858 | 0.2583 | 0 |
| `weak_scaffold_sql_retrieval_repair_v1` | 5 | 0.1797 | 0.36 | 0.0 | 0.1252 | 0 |
| `weak_scaffold_sql_retrieval_v1` | 5 | 0.1796 | 0.36 | 0.0 | 0.1252 | 0 |
| `weak_scaffold_sql_unit_tested_v1` | 5 | 0.1797 | 0.36 | 0.0 | 0.1252 | 0 |

- Small-model lift score: `0.334`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
