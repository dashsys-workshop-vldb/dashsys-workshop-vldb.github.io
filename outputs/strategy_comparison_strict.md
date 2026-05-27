# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0190 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4542 | 2.11 | 2.3340 | 1358 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5903 | 1.17 | 1.5337 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6543 | 1.46 | 1.7697 | 791 |
| TEMPLATE_FIRST | 0.6850 | 0.6474 | 1.71 | 1.9380 | 1177 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00520 | 0.00370 | 0.00150 | 0.00110 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00820 | 0.00130 | 2.29240 | 0.01380 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00290 | 0.00050 | 1.50280 | 0.01180 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00290 | 0.00070 | 1.73720 | 0.01200 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00300 | 0.00080 | 1.90420 | 0.01230 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
