# Tool Calling Objective Functions

- Organizer weights known: `False`
- Official overall score claim: `False`

## Composite Scenarios
- `correctness_dominant`: {'formula': '0.80 correctness + 0.20 efficiency'}
- `balanced`: {'formula': '0.60 correctness + 0.40 efficiency'}
- `efficiency_sensitive`: {'formula': '0.50 correctness + 0.50 efficiency'}
- `no_regression_efficiency`: {'requirement': 'correctness >= baseline', 'rank_by': 'efficiency_score_equal_weight'}
- `pareto_frontier`: {'requirement': 'correctness >= baseline and at least one efficiency metric improves'}
