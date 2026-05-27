# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0179 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.4997 | 0.4596 | 2.11 | 0.6860 | 1367 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6184 | 0.5943 | 1.17 | 0.3594 | 996 |
| SQL_FIRST_API_VERIFY | 0.6850 | 0.6586 | 1.46 | 0.4538 | 799 |
| TEMPLATE_FIRST | 0.6850 | 0.6521 | 1.71 | 0.4823 | 1186 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00520 | 0.00310 | 0.00130 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00870 | 0.00160 | 0.64790 | 0.01350 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00300 | 0.00050 | 0.33160 | 0.01080 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00320 | 0.00080 | 0.42530 | 0.01140 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00280 | 0.00080 | 0.45440 | 0.01100 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
