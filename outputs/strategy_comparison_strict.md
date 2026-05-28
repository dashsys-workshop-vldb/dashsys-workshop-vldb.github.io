# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6564 | 1.46 | 1.1217 | 791 |
| SQL_FIRST_API_VERIFY_HYBRID_ANSWER | 0.6752 | 0.6477 | 1.46 | 0.8337 | 778 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_FIRST_API_VERIFY_HYBRID_ANSWER`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00550 | 0.00250 | 1.08980 | 0.01190 |
| SQL_FIRST_API_VERIFY_HYBRID_ANSWER | 824 | 1466 | 0.00290 | 0.00170 | 0.78330 | 0.01840 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
