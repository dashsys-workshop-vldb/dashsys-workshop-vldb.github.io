# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6812 | 0.6562 | 1.46 | 0.0250 | 797 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_FIRST_API_VERIFY`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00810 | 0.00300 | 0.00180 | 0.00120 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
