# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0174 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4558 | 2.11 | 1.8340 | 1367 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5926 | 1.17 | 0.8677 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6514 | 1.46 | 1.7360 | 1151 |
| TEMPLATE_FIRST | 0.6850 | 0.6480 | 1.71 | 1.7294 | 1186 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00590 | 0.00250 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00860 | 0.00200 | 1.79340 | 0.01370 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00350 | 0.00060 | 0.83780 | 0.01150 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00360 | 0.00080 | 1.70300 | 0.01230 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00350 | 0.00080 | 1.69650 | 0.01230 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
