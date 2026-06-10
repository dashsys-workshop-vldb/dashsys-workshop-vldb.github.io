# Weak Harness Answer Regression Analysis

Diagnostic-only comparison of api-recovery v1, answer-fallback v3, and `weak_harness_full_v1`.

- Run label: `public_dev_full`
- Rows compared: `35`
- Dominant category: `no_clear_regression`
- Safest targeted fix: `balanced_sql_api_style_preserve_renderer`
- Regressed rows vs v1: `['example_004', 'example_006', 'example_007', 'example_008', 'example_013', 'example_016', 'example_019', 'example_022', 'example_023', 'example_024', 'example_025', 'example_026', 'example_027', 'example_028', 'example_030', 'example_031']`

## Category Counts

- `no_clear_regression`: `19`
- `omitted_sql_evidence`: `3`
- `wrong_answer_shape`: `13`

## Mode Summaries

| Mode | Strict | SQL | API | Answer | Tokens | Runtime | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `weak_harness_full_v1` | 0.2771 | 0.12 | 0.6241 | 0.2188 | 4990.7714 | 2.1267 | 0 |
| `weak_scaffold_answer_fallback_v3` | 0.2773 | 0.12 | 0.6241 | 0.2188 | 4991.8857 | 1.9501 | 0 |
| `weak_scaffold_api_recovery_v1` | 0.2882 | 0.06 | 0.6241 | 0.2262 | 3179.2857 | 2.1432 | 0 |

## Row Categories

| Query | Category | Answer delta vs v1 | SQL delta vs v1 | API delta vs v1 |
| --- | --- | ---: | ---: | ---: |
| `example_000` | `no_clear_regression` | 0.0216 | 0.0 | 0.0 |
| `example_001` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_002` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_003` | `no_clear_regression` | 0.0788 | 0.9 | 0.0 |
| `example_004` | `wrong_answer_shape` | -0.001 | 0.0 | 0.0 |
| `example_005` | `no_clear_regression` | 0.0006 | 0.0 | 0.0 |
| `example_006` | `wrong_answer_shape` | -0.002 | 0.0 | 0.0 |
| `example_007` | `wrong_answer_shape` | -0.0046 | 0.0 | 0.0 |
| `example_008` | `omitted_sql_evidence` | -0.4481 | 0.0 | 0.0 |
| `example_009` | `no_clear_regression` | 0.0016 | 0.0 | 0.0 |
| `example_010` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_011` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_012` | `no_clear_regression` | 0.0015 | 0.0 | 0.0 |
| `example_013` | `wrong_answer_shape` | -0.0013 | 0.0 | 0.0 |
| `example_014` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_015` | `no_clear_regression` | 0.0039 | 0.0 | 0.0 |
| `example_016` | `wrong_answer_shape` | -0.0103 | 0.0 | 0.0 |
| `example_017` | `no_clear_regression` | 0.0035 | 0.0 | 0.0 |
| `example_018` | `no_clear_regression` | 0.1272 | 0.0 | 0.0 |
| `example_019` | `wrong_answer_shape` | -0.0168 | 0.0 | 0.0 |
| `example_020` | `no_clear_regression` | 0.0032 | 0.0 | 0.0 |
| `example_021` | `no_clear_regression` | 0.0008 | 0.0 | 0.0 |
| `example_022` | `wrong_answer_shape` | -0.0004 | 0.0 | 0.0 |
| `example_023` | `wrong_answer_shape` | -0.0008 | 0.0 | 0.0 |
| `example_024` | `wrong_answer_shape` | -0.0005 | 0.0 | 0.0 |
| `example_025` | `wrong_answer_shape` | -0.0041 | 0.0 | 0.0 |
| `example_026` | `wrong_answer_shape` | -0.0036 | 0.0 | 0.0 |
| `example_027` | `wrong_answer_shape` | -0.005 | 0.0 | 0.0 |
| `example_028` | `omitted_sql_evidence` | -0.001 | 0.0 | 0.0 |
| `example_029` | `no_clear_regression` | 0.0003 | 0.0 | 0.0 |
| `example_030` | `wrong_answer_shape` | -0.0029 | 0.0 | 0.0 |
| `example_031` | `omitted_sql_evidence` | -0.002 | 0.0 | 0.0 |
| `example_032` | `no_clear_regression` | 0.0 | 0.0 | 0.0 |
| `example_033` | `no_clear_regression` | 0.0009 | 0.0 | 0.0 |
| `example_034` | `no_clear_regression` | 0.0011 | 0.0 | 0.0 |
