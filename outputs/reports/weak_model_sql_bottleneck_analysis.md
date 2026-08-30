# Weak Model SQL Bottleneck Analysis

Diagnostic-only analysis of weak scaffold SQL failures. No runtime promotion.

- Variant: `weak_scaffold_api_recovery_v1`
- Rows with SQL score: `15`
- Average SQL score: `0.06`
- Dominant SQL bottleneck: `SQL_valid_but_wrong_semantics`
- Fix layer: `semantic_sql_ranking_or_schema_retrieval`
- Safe next candidate: `add semantic SQL candidate ranking before execution`

## Failure Distribution

- `SQL_result_not_used`: `4`
- `SQL_valid_but_wrong_semantics`: `8`
- `no_sql_when_needed`: `3`

## Examples

- `example_000`: `SQL_result_not_used` SQL `0.0`
- `example_001`: `SQL_result_not_used` SQL `0.0`
- `example_002`: `SQL_valid_but_wrong_semantics` SQL `0.0`
- `example_003`: `SQL_valid_but_wrong_semantics` SQL `0.0`
- `example_004`: `SQL_result_not_used` SQL `0.9`
- `example_005`: `no_sql_when_needed` SQL `0.0`
- `example_006`: `SQL_valid_but_wrong_semantics` SQL `0.0`
- `example_007`: `SQL_valid_but_wrong_semantics` SQL `0.0`
- `example_008`: `no_sql_when_needed` SQL `0.0`
- `example_009`: `SQL_result_not_used` SQL `0.0`
- `example_010`: `SQL_valid_but_wrong_semantics` SQL `0.0`
- `example_011`: `SQL_valid_but_wrong_semantics` SQL `0.0`
