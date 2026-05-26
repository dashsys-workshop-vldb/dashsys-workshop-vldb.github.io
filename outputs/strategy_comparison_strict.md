# Strategy Comparison

| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |
|---|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 0.2989 | 0.2801 | 1.00 | 0.0181 | 757 |
| LLM_FREE_AGENT_BASELINE | 0.5062 | 0.4633 | 2.11 | 1.5992 | 1342 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6249 | 0.5979 | 1.17 | 1.2718 | 971 |
| SQL_FIRST_API_VERIFY | 0.6915 | 0.6621 | 1.46 | 1.3502 | 798 |
| TEMPLATE_FIRST | 0.6915 | 0.6573 | 1.71 | 0.9256 | 1160 |

- Best correctness: `SQL_FIRST_API_VERIFY`
- Best efficiency: `SQL_ONLY_BASELINE`
- Best overall: `SQL_FIRST_API_VERIFY`

## Token Context

| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |
|---|---:|---:|---:|---:|---:|---:|
| SQL_ONLY_BASELINE | 818 | 1460 | 0.00570 | 0.00300 | 0.00140 | 0.00100 |
| LLM_FREE_AGENT_BASELINE | 6020 | 8031 | 0.00850 | 0.00140 | 1.55990 | 0.01260 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | 822 | 1464 | 0.00330 | 0.00060 | 1.24240 | 0.01040 |
| SQL_FIRST_API_VERIFY | 818 | 1460 | 0.00340 | 0.00080 | 1.31820 | 0.01120 |
| TEMPLATE_FIRST | 816 | 1458 | 0.00340 | 0.00080 | 0.89470 | 0.01130 |

## Recommended Next Focus
- Improve entity extraction and join-template coverage.
- Add endpoint-specific param selection from observed gold API patterns.
