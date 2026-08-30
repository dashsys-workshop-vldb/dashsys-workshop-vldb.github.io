# Pure LLM SQL Semantic Verifier Trial

Diagnostic-only shadow trial. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Summary
- `variants_tested`: `['structured_sql_plan_semantic_verified_v1', 'structured_sql_plan_semantic_repair_v1', 'sql_grounded_answer_v1', 'conservative_sql_first_semantic_v1']`
- `best_variant_by_strict`: `structured_sql_plan_semantic_verified_v1`
- `best_strict_score`: `0.0802`
- `best_sql_score`: `0.18`
- `unsupported_claims_total`: `0`
- `sql_score_improved_over_0_18`: `False`
- `strict_improved_over_0_1074`: `False`
- `full_35_row_eval_allowed`: `False`
- `full_35_row_eval_run`: `False`
- `recommendation`: `pure_llm_semantic_sql_shadow_only_no_promotion`

## Variant Scores
- `structured_sql_plan_semantic_verified_v1`: strict `0.0802`, SQL `0.0`, API `0.5533`, answer `0.1763`, unsupported `0`, compile `0.5`, SQL validation `0.2`
- `structured_sql_plan_semantic_repair_v1`: strict `0.0727`, SQL `0.0`, API `0.5533`, answer `0.1763`, unsupported `0`, compile `0.5`, SQL validation `0.2`
- `sql_grounded_answer_v1`: strict `0.0633`, SQL `0.0`, API `0.5533`, answer `0.1763`, unsupported `0`, compile `0.5`, SQL validation `0.2`
- `conservative_sql_first_semantic_v1`: strict `0.055`, SQL `0.18`, API `0.0`, answer `0.2398`, unsupported `0`, compile `0.6`, SQL validation `0.6`

## Final Row-Level Semantic Failures
- `example_000`: `wrong_columns`; SQL `0.0`; answer `0.2176`; root cause: The SQL plan selected an updated timestamp instead of a published timestamp such as LASTDEPLOYEDTIME.
- `example_001`: `no_executable_sql`; SQL `0.0`; answer `0.1739`; root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
- `example_002`: `wrong_table`; SQL `0.0`; answer `0.3392`; root cause: The SQL plan passed validation but selected a table or SQL shape that did not match the requested local entity.
- `example_003`: `sql_result_not_used`; SQL `0.9`; answer `0.2553`; root cause: The SQL query produced useful rows, but final answer synthesis ignored or underused those rows.
- `example_004`: `no_executable_sql`; SQL `0.0`; answer `0.2131`; root cause: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

## Decision
No full 35-row Pure LLM eval was run because no bounded variant met both gates: strict score > `0.1074` and SQL score > `0.18` with unsupported claims `0`.
