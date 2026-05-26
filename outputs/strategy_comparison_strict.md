# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0182 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4585 | 2.11 | 1.0114 | 1367 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5941 | 1.17 | 0.4188 | 996 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6582 | 1.46 | 0.5676 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6520 | 1.71 | 0.4897 | 1186 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00570 | 0.00300 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00840 | 0.00140 | 0.97260 | 0.01330 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00350 | 0.00060 | 0.38990 | 0.01160 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00330 | 0.00080 | 0.53760 | 0.01150 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00320 | 0.00080 | 0.45860 | 0.01200 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
