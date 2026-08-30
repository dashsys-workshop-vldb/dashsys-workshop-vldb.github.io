# Weak Model Answer Grounding Regression Analysis

Diagnostic-only comparison of `weak_scaffold_api_recovery_v1`, SQL-lift v2, and v3 answer-grounding variants.

- Run label: `public_dev_limit_10`
- Rows compared: `10`
- Rows where v2 SQL improved but answer regressed: `[]`
- Safest fix candidate: `balanced_sql_api_answer_v3_with_deterministic_evidence_fallback`

## Category Counts

- `answer_shape_weaker`: `1`
- `no_clear_answer_regression`: `8`
- `sql_api_arbitration_wrong`: `1`

## Mode Summaries

| Mode | Strict | SQL | API | Answer | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: |
| `weak_scaffold_answer_fallback_v3` | 0.2596 | 0.18 | 0.8517 | 0.2359 | 0 |
| `weak_scaffold_api_recovery_v1` | 0.2475 | 0.09 | 0.8517 | 0.2712 | 0 |
| `weak_scaffold_balanced_sql_api_answer_v3` | 0.2591 | 0.18 | 0.8517 | 0.2359 | 0 |
| `weak_scaffold_balanced_sql_api_v2` | 0.2471 | 0.18 | 0.8517 | 0.2077 | 0 |
| `weak_scaffold_sql_lift_api_recovery_v3` | 0.2597 | 0.18 | 0.8517 | 0.2359 | 0 |

## Row Categories

| Query | Category | SQL delta | Answer delta | Strict delta |
| --- | --- | ---: | ---: | ---: |
| `example_000` | `no_clear_answer_regression` | 0.0 | 0.0216 | 0.0235 |
| `example_001` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0125 |
| `example_002` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0067 |
| `example_003` | `no_clear_answer_regression` | 0.9 | 0.1365 | 0.3811 |
| `example_004` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0062 |
| `example_005` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0099 |
| `example_006` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0109 |
| `example_007` | `answer_shape_weaker` | 0.0 | -0.0025 | 0.006 |
| `example_008` | `sql_api_arbitration_wrong` | 0.0 | -0.791 | -0.3655 |
| `example_009` | `no_clear_answer_regression` | 0.0 | 0.0 | -0.0027 |
