# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_dashagent_current` | 10 | 0.7052 | 0.93 | 0.8919 | 0.4109 | 0 |
| `guided_weak_llm` | 10 | 0.1458 | 0.09 | 0.3283 | 0.334 | 0 |
| `raw_weak_llm` | 10 | 0.076 | 0.0 | 0.3227 | 0.2692 | 0 |
| `weak_harness_answer_and_efficiency_v2` | 10 | 0.2758 | 0.18 | 0.8517 | 0.2367 | 0 |

- Small-model lift score: `0.1998`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
