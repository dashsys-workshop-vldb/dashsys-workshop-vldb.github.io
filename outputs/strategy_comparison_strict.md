# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0172 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4518 | 2.11 | 3.4919 | 1366 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5885 | 1.17 | 2.1032 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6520 | 1.46 | 2.4725 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6463 | 1.71 | 2.5818 | 1185 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00560 | 0.00240 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00820 | 0.00180 | 3.45220 | 0.01360 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00330 | 0.00060 | 2.07510 | 0.01140 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00320 | 0.00070 | 2.44210 | 0.01200 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00330 | 0.00080 | 2.55140 | 0.01190 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
