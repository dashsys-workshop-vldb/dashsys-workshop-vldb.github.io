# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 35 | 0.6585 | 0.9333 | 0.9791 | 0.3207 | 0 |
| `guided_weak_llm` | 35 | 0.2244 | 0.12 | 0.4287 | 0.2631 | 2 |
| `raw_weak_llm` | 35 | 0.1596 | 0.0 | 0.3397 | 0.2337 | 1 |
| `weak_scaffold_api_recovery_v1` | 35 | 0.2873 | 0.06 | 0.6241 | 0.2201 | 0 |

- Small-model lift score: `0.1277`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
