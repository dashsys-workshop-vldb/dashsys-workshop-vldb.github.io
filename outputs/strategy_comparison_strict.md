# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6581 | 1.46 | 0.5986 | 799 |
| STAGED_EVIDENCE_APPLIED_TRIAL | 0.6641 | 0.6394 | 1.34 | 0.4345 | 775 |
| POST_SQL_DETERMINISTIC_APPLIED_TRIAL | 0.6641 | 0.6393 | 1.34 | 0.4577 | 775 |
| COMBINED_SAFE_APPLIED_TRIAL | 0.6641 | 0.6392 | 1.34 | 0.4891 | 775 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `STAGED_EVIDENCE_APPLIED_TRIAL`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00520 | 0.00190 | 0.56850 | 0.01170 |
| STAGED_EVIDENCE_APPLIED_TRIAL | 823 | 1465 | 0.00240 | 0.00170 | 0.39760 | 0.01150 |
| POST_SQL_DETERMINISTIC_APPLIED_TRIAL | 824 | 1466 | 0.00240 | 0.00170 | 0.42190 | 0.01250 |
| COMBINED_SAFE_APPLIED_TRIAL | 822 | 1464 | 0.00240 | 0.00170 | 0.44820 | 0.01100 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
