# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6579 | 1.46 | 0.6887 | 791 |
| SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER | 0.6851 | 0.6487 | 1.46 | 3.4665 | 791 |

- Best correctness: `SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER`
- Best efficiency: `SQL_FIRST_API_VERIFY`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00510 | 0.00250 | 0.65520 | 0.01250 |
| SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER | 824 | 1466 | 0.00260 | 0.00240 | 0.51000 | 2.92240 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
