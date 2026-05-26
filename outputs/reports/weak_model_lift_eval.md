# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `evidence_guarded_weak_agent` | 5 | 0.1171 | 0.18 | 0.0 | 0.1081 | 0 |
| `full_dashagent_current` | 5 | 0.7025 | 0.9 | 1.0 | 0.3781 | 0 |
| `guided_weak_llm` | 5 | 0.1603 | 0.18 | 0.1492 | 0.3288 | 0 |
| `raw_weak_llm` | 5 | 0.04 | 0.0 | 0.1879 | 0.2411 | 0 |
| `slot_to_sql_compiled_agent` | 5 | 0.1167 | 0.18 | 0.0 | 0.1081 | 0 |
| `weak_full_dashagent_scaffold` | 5 | 0.1171 | 0.18 | 0.0 | 0.1081 | 0 |
| `weak_semantic_slots_only` | 5 | 0.0233 | 0.0 | 0.0 | 0.0731 | 0 |

- Small-model lift score: `0.0771`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
