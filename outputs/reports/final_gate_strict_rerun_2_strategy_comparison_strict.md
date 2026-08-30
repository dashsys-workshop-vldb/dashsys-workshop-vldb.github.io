# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0181 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4998 | 0.4505 | 2.11 | 3.9973 | 1358 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6185 | 0.5879 | 1.17 | 2.7042 | 995 |
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6500 | 1.46 | 3.2873 | 791 |
| TEMPLATE_FIRST | 0.6851 | 0.6459 | 1.71 | 2.5392 | 1176 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00500 | 0.00290 | 0.00130 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00770 | 0.00130 | 3.95260 | 0.01480 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00370 | 0.00060 | 2.67260 | 0.01140 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00280 | 0.00070 | 3.25270 | 0.01250 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00290 | 0.00080 | 2.50320 | 0.01280 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
