# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0175 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4998 | 0.4596 | 2.11 | 0.6814 | 1370 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6185 | 0.5943 | 1.17 | 0.3565 | 996 |
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6555 | 1.46 | 0.5117 | 1153 |
| TEMPLATE_FIRST | 0.6851 | 0.6522 | 1.71 | 0.4701 | 1188 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00580 | 0.00240 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00880 | 0.00180 | 0.64100 | 0.01370 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00340 | 0.00060 | 0.32780 | 0.01160 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00330 | 0.00080 | 0.48080 | 0.01200 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00340 | 0.00080 | 0.43930 | 0.01200 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
