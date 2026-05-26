# Weak Model Lift Eval

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Mode | Rows | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `evidence_guarded_weak_agent` | 35 | 0.1853 | 0.06 | 0.1717 | 0.2811 | 0 |
| `full_dashagent_current` | 35 | 0.658 | 0.9333 | 0.9791 | 0.3207 | 0 |
| `guided_weak_llm` | 35 | 0.2244 | 0.12 | 0.4287 | 0.2631 | 2 |
| `raw_weak_llm` | 35 | 0.1596 | 0.0 | 0.3397 | 0.2337 | 1 |
| `slot_to_sql_compiled_agent` | 35 | 0.1255 | 0.06 | 0.1717 | 0.1457 | 0 |
| `weak_full_dashagent_scaffold` | 35 | 0.1852 | 0.06 | 0.1717 | 0.2811 | 0 |
| `weak_scaffold_api_recovery_v1` | 35 | 0.2869 | 0.06 | 0.6241 | 0.2263 | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 35 | 0.2739 | 0.12 | 0.6241 | 0.2105 | 0 |
| `weak_semantic_slots_only` | 35 | 0.0343 | 0.0 | 0.0 | 0.0855 | 0 |

- Small-model lift score: `0.1273`
- Recommendation: `weak_model_scaffold_improved_keep_shadow`
