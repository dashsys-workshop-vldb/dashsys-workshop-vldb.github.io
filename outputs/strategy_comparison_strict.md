# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0173 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4590 | 2.11 | 0.8559 | 1366 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5939 | 1.17 | 0.4626 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6580 | 1.46 | 0.6133 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6517 | 1.71 | 0.6007 | 1185 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00600 | 0.00250 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00900 | 0.00200 | 0.81800 | 0.01330 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00400 | 0.00060 | 0.43560 | 0.01090 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00350 | 0.00080 | 0.58340 | 0.01170 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00380 | 0.00080 | 0.57210 | 0.01170 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
