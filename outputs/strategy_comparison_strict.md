# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2983 | 0.2794 | 1.00 | 0.0377 | 756 |
| LLM_FREE_AGENT_BASELINE | 0.4941 | 0.4589 | 2.11 | 0.0537 | 1027 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6136 | 0.5924 | 1.17 | 0.0334 | 770 |
| SQL_FIRST_API_VERIFY | 0.6805 | 0.6552 | 1.46 | 0.0308 | 835 |
| TEMPLATE_FIRST | 0.6805 | 0.6517 | 1.71 | 0.0394 | 868 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 819 | 1463 | 0.02190 | 0.00730 | 0.00360 | 0.00230 |
| LLM_FREE_AGENT_BASELINE | 5782 | 7759 | 0.02550 | 0.00520 | 0.00370 | 0.00390 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 823 | 1467 | 0.00740 | 0.00200 | 0.00100 | 0.00180 |
| SQL_FIRST_API_VERIFY | 819 | 1463 | 0.00720 | 0.00230 | 0.00130 | 0.00190 |
| TEMPLATE_FIRST | 817 | 1461 | 0.00720 | 0.00240 | 0.00150 | 0.00200 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
