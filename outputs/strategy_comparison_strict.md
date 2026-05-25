# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0175 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4998 | 0.4593 | 2.11 | 0.7820 | 1370 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6185 | 0.5937 | 1.17 | 0.5336 | 996 |
| SQL_FIRST_API_VERIFY | 0.6851 | 0.6554 | 1.46 | 0.5356 | 1153 |
| TEMPLATE_FIRST | 0.6851 | 0.6520 | 1.71 | 0.5277 | 1188 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00650 | 0.00270 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00870 | 0.00180 | 0.73930 | 0.01420 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00380 | 0.00060 | 0.50390 | 0.01130 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00370 | 0.00080 | 0.50130 | 0.01260 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00370 | 0.00080 | 0.49510 | 0.01230 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
