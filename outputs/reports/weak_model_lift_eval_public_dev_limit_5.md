# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 5 | 0.7025 | 0.9 | 1.0 | 0.3781 | 0 |
| `guided_weak_llm` | 5 | 0.1603 | 0.18 | 0.1492 | 0.3288 | 0 |
| `raw_weak_llm` | 5 | 0.04 | 0.0 | 0.1879 | 0.2411 | 0 |
| `weak_scaffold_answer_grounded_v1` | 5 | 0.3033 | 0.18 | 0.9858 | 0.2372 | 0 |
| `weak_scaffold_api_recovery_v1` | 5 | 0.3079 | 0.18 | 0.9858 | 0.2372 | 0 |
| `weak_scaffold_balanced_full_v1` | 5 | 0.2944 | 0.18 | 0.9858 | 0.2163 | 0 |
| `weak_scaffold_balanced_sql_api_v1` | 5 | 0.3063 | 0.18 | 0.9858 | 0.2372 | 0 |

- Small-model lift score: `0.2679`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
