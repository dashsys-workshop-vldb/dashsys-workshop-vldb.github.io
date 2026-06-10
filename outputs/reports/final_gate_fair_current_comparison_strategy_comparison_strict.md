# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6492 | 1.46 | 3.6795 | 791 |
| COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE | 0.6851 | 0.6513 | 1.46 | 2.7249 | 791 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`
- Best overall: `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00500 | 0.00180 | 3.64430 | 0.01260 |
| COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE | 828 | 1470 | 0.00250 | 0.00170 | 2.68240 | 0.01250 |

## Recommended Next Focus
- Inspect failed examples and add deterministic routing/schema selection rules before adding agent complexity.
