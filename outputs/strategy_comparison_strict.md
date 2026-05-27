# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0181 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4998 | 0.4525 | 2.11 | 3.4011 | 1358 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6185 | 0.5882 | 1.17 | 2.4126 | 995 |
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6515 | 1.46 | 2.8805 | 791 |
| TEMPLATE_FIRST | 0.6851 | 0.6458 | 1.71 | 2.7134 | 1176 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00500 | 0.00300 | 0.00130 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00790 | 0.00130 | 3.35770 | 0.01470 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00300 | 0.00050 | 2.38110 | 0.01160 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00290 | 0.00080 | 2.84620 | 0.01230 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00300 | 0.00100 | 2.67920 | 0.01190 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
