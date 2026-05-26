# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0172 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4568 | 2.11 | 1.5331 | 1366 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5912 | 1.17 | 1.2671 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6557 | 1.46 | 1.3040 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6497 | 1.71 | 1.1961 | 1185 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00570 | 0.00240 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00880 | 0.00170 | 1.49030 | 0.01470 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00390 | 0.00060 | 1.23700 | 0.01170 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00380 | 0.00080 | 1.27020 | 0.01290 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00380 | 0.00080 | 1.16500 | 0.01190 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
