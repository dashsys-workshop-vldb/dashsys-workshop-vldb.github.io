# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2800 | 1.00 | 0.0175 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4597 | 2.11 | 0.6591 | 1366 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5942 | 1.17 | 0.3707 | 995 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6585 | 1.46 | 0.4736 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6521 | 1.71 | 0.4644 | 1185 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00600 | 0.00250 | 0.00150 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00900 | 0.00180 | 0.61870 | 0.01380 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00370 | 0.00060 | 0.34230 | 0.01110 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00370 | 0.00080 | 0.44220 | 0.01160 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00360 | 0.00080 | 0.43310 | 0.01180 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
