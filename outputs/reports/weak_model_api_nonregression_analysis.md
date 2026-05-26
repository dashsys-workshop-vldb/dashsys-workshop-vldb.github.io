# Weak Model API Non-Regression Analysis

Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.

| Query | Root cause | Raw API | Guided API | Scaffold API | Full API | Scaffold calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `example_000` | `no_clear_api_regression` | None | None | None | None | 0 |
| `example_001` | `endpoint_not_selected` | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| `example_002` | `endpoint_not_selected` | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| `example_003` | `endpoint_not_selected` | 0.5637 | 0.4475 | 0.0 | 1.0 | 0 |
| `example_004` | `no_clear_api_regression` | None | None | None | None | 0 |

- Dominant loss stage: `endpoint_not_selected`
- Safest fix candidate: `balanced_sql_api_evidence_need_plus_catalog_endpoint_selection`
