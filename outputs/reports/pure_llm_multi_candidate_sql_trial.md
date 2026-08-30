# Pure LLM Multi-Candidate SQL Trial

Diagnostic-only shadow report. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Summary
- `variants_tested`: `['multi_candidate_sql_plan_v1', 'multi_candidate_sql_plan_with_probe_v1', 'multi_candidate_sql_grounded_answer_v1', 'conservative_sql_first_multi_candidate_v1']`
- `best_variant_by_strict`: `multi_candidate_sql_plan_v1`
- `best_bounded_strict_score`: `0.0675`
- `best_bounded_sql_score`: `0`
- `strict_improved_over_0_1074`: `False`
- `sql_improved_over_0_18`: `False`
- `unsupported_claims_total`: `0`
- `full_35_row_eval_allowed`: `False`
- `full_35_row_eval_run`: `False`
- `pure_llm_shadow_only`: `True`
- `recommendation`: `pure_llm_multi_candidate_shadow_only_no_promotion`

## Variant Scores

| Variant | Strict | SQL | API | Answer | Unsupported | Compile | SQL validation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `multi_candidate_sql_plan_v1` | 0.0675 | 0.0 | 0.5533 | 0.1763 | 0 | 0.0 | 0.0 |
| `multi_candidate_sql_plan_with_probe_v1` | 0.0609 | 0.0 | 0.5533 | 0.1706 | 0 | 0.0 | 0.0 |
| `multi_candidate_sql_grounded_answer_v1` | 0.0637 | 0.0 | 0.5533 | 0.1763 | 0 | 0.0 | 0.0 |
| `conservative_sql_first_multi_candidate_v1` | -0.0177 | 0.0 | 0.0 | 0.2375 | 0 | 0.2 | 0.2 |

## Row Before/After
- `example_000`: previous `wrong_columns`, current `no_executable_sql`, SQL `0.0`, answer `0.2176`, candidates `3`, SQL evidence available/used `False`/`False`, remaining: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
- `example_001`: previous `no_executable_sql`, current `no_executable_sql`, SQL `0.0`, answer `0.1739`, candidates `3`, SQL evidence available/used `False`/`False`, remaining: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
- `example_002`: previous `wrong_table`, current `wrong_table`, SQL `0.0`, answer `0.3278`, candidates `3`, SQL evidence available/used `True`/`True`, remaining: The SQL plan passed validation but selected a table or SQL shape that did not match the requested local entity.
- `example_003`: previous `sql_result_not_used`, current `no_executable_sql`, SQL `0.0`, answer `0.2553`, candidates `3`, SQL evidence available/used `False`/`False`, remaining: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.
- `example_004`: previous `no_executable_sql`, current `no_executable_sql`, SQL `0.0`, answer `0.2131`, candidates `3`, SQL evidence available/used `False`/`False`, remaining: The structured SQL plan or repair output did not compile to executable SQL before strict scoring.

## Decision
Full 35-row Pure LLM eval was not run because no bounded variant exceeded strict `0.1074` with SQL score above `0.18` and unsupported claims `0`. Pure LLM remains shadow-only.
