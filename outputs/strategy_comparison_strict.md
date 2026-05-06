# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2983 | 0.2795 | 1.00 | 0.0125 | 751 |
| LLM_FREE_AGENT_BASELINE | 0.4879 | 0.4529 | 2.11 | 0.0187 | 1019 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6074 | 0.5864 | 1.17 | 0.0107 | 762 |
| SQL_FIRST_API_VERIFY | 0.6743 | 0.6486 | 1.46 | 0.0112 | 894 |
| TEMPLATE_FIRST | 0.6743 | 0.6457 | 1.71 | 0.0114 | 860 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 819 | 1463 | 0.00770 | 0.00260 | 0.00130 | 0.00120 |
| LLM_FREE_AGENT_BASELINE | 5782 | 7759 | 0.00770 | 0.00170 | 0.00130 | 0.00130 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 823 | 1467 | 0.00280 | 0.00060 | 0.00040 | 0.00050 |
| SQL_FIRST_API_VERIFY | 819 | 1463 | 0.00260 | 0.00090 | 0.00040 | 0.00050 |
| TEMPLATE_FIRST | 817 | 1461 | 0.00280 | 0.00120 | 0.00050 | 0.00060 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
