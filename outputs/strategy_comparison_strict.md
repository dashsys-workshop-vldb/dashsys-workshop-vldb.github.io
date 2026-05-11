# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2983 | 0.2794 | 1.00 | 0.0131 | 756 |
| LLM_FREE_AGENT_BASELINE | 0.4941 | 0.4590 | 2.11 | 0.0199 | 1027 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6136 | 0.5925 | 1.17 | 0.0115 | 770 |
| SQL_FIRST_API_VERIFY | 0.6805 | 0.6553 | 1.46 | 0.0119 | 835 |
| TEMPLATE_FIRST | 0.6805 | 0.6518 | 1.71 | 0.0122 | 868 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 819 | 1463 | 0.00510 | 0.00250 | 0.00130 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 5782 | 7759 | 0.00780 | 0.00190 | 0.00140 | 0.00150 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 823 | 1467 | 0.00280 | 0.00060 | 0.00040 | 0.00070 |
| SQL_FIRST_API_VERIFY | 819 | 1463 | 0.00270 | 0.00090 | 0.00040 | 0.00070 |
| TEMPLATE_FIRST | 817 | 1461 | 0.00270 | 0.00090 | 0.00050 | 0.00070 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
