# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0180 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4998 | 0.4514 | 2.11 | 3.6283 | 1358 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6185 | 0.5886 | 1.17 | 2.2291 | 995 |
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6522 | 1.46 | 2.5058 | 791 |
| TEMPLATE_FIRST | 0.6851 | 0.6464 | 1.71 | 2.9909 | 1176 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00530 | 0.00290 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00780 | 0.00130 | 3.58470 | 0.01400 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00290 | 0.00050 | 2.19820 | 0.01140 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00290 | 0.00070 | 2.47090 | 0.01280 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00290 | 0.00080 | 2.95550 | 0.01250 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
