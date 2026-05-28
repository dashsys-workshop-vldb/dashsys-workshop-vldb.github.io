# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6513 | 1.46 | 2.9681 | 791 |
| SQL_FIRST_API_VERIFY_HYBRID_ANSWER | 0.6850 | 0.6518 | 1.46 | 2.4977 | 791 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_FIRST_API_VERIFY_HYBRID_ANSWER`
- Best overall: `SQL_FIRST_API_VERIFY_HYBRID_ANSWER`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00510 | 0.00240 | 2.93660 | 0.01200 |
| SQL_FIRST_API_VERIFY_HYBRID_ANSWER | 824 | 1466 | 0.00220 | 0.00160 | 2.44740 | 0.01880 |

## Recommended Next Focus
- Inspect failed examples and add deterministic routing/schema selection rules before adding agent complexity.
