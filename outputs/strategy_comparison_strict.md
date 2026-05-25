# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0176 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4578 | 2.11 | 1.2301 | 1368 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5936 | 1.17 | 0.5819 | 996 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6572 | 1.46 | 0.8732 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6512 | 1.71 | 0.7521 | 1187 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00560 | 0.00250 | 0.00140 | 0.00110 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00840 | 0.00190 | 1.18940 | 0.01390 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00300 | 0.00060 | 0.55200 | 0.01150 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00330 | 0.00070 | 0.84050 | 0.01220 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00310 | 0.00080 | 0.71960 | 0.01220 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
