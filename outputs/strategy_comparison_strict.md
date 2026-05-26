# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2800 | 1.00 | 0.0208 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4595 | 2.11 | 0.6961 | 1367 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5942 | 1.17 | 0.3757 | 996 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6584 | 1.46 | 0.5088 | 800 |
| TEMPLATE_FIRST | 0.6850 | 0.6521 | 1.71 | 0.4659 | 1186 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00520 | 0.00310 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00840 | 0.00150 | 0.65350 | 0.01410 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00290 | 0.00050 | 0.34630 | 0.01130 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00290 | 0.00070 | 0.47540 | 0.01250 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00320 | 0.00080 | 0.43230 | 0.01180 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
