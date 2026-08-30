# Pure LLM Tool-Choice Bounded Variant Comparison

Diagnostic-only comparison. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

| Variant | Strict | SQL | API | Answer | Unsupported | Compile | SQL Validation | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `structured_sql_plan_with_tool_choice_guard_v1` | 0.0505 | 0.0 | 0.5533 | 0.1338 | 0 | 0.5 | 0.2 | 23.5413 |
| `sql_first_when_validator_high_confidence_v1` | 0.0276 | 0.18 | 0.0 | 0.1476 | 0 | 0.75 | 0.6 | 19.3351 |
| `api_only_only_when_sql_unavailable_v1` | 0.0222 | 0.18 | 0.0 | 0.1476 | 0 | 0.75 | 0.6 | 30.76 |

- Best SQL variant: `sql_first_when_validator_high_confidence_v1`
- Best strict variant: `structured_sql_plan_with_tool_choice_guard_v1`
- Recommendation: `pure_llm_remains_shadow_only_tool_choice_improved_sql_semantics_still_weak`
