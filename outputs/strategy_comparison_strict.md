# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2983 | 0.2794 | 1.00 | 0.0248 | 756 |
| LLM_FREE_AGENT_BASELINE | 0.4941 | 0.4589 | 2.11 | 0.0374 | 1027 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6136 | 0.5925 | 1.17 | 0.0215 | 770 |
| SQL_FIRST_API_VERIFY | 0.6805 | 0.6552 | 1.46 | 0.0228 | 835 |
| TEMPLATE_FIRST | 0.6805 | 0.6517 | 1.71 | 0.0230 | 868 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 819 | 1463 | 0.00900 | 0.00450 | 0.00240 | 0.00200 |
| LLM_FREE_AGENT_BASELINE | 5782 | 7759 | 0.01490 | 0.00350 | 0.00240 | 0.00280 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 823 | 1467 | 0.00510 | 0.00120 | 0.00070 | 0.00110 |
| SQL_FIRST_API_VERIFY | 819 | 1463 | 0.00520 | 0.00160 | 0.00080 | 0.00130 |
| TEMPLATE_FIRST | 817 | 1461 | 0.00520 | 0.00170 | 0.00090 | 0.00130 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
