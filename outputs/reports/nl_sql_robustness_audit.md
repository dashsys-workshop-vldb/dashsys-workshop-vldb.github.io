# NL-to-SQL Robustness Audit

Diagnostic-only robustness audit for `SQL_FIRST_API_VERIFY` SQL planning. No packaged runtime promotion is made.

Higher score is not considered meaningful unless robustness and generalization gates pass.

## Metrics

- Template hit rate: `0.3512`
- Template miss rate: `0.6488`
- Fallback success rate: `1.0`
- SQL validation pass rate: `0.5735`
- SQL execution pass rate: `0.5735`
- Answer correctness proxy: `0.5735`
- Route stability: `0.9825`
- Table selection stability: `0.9719`
- Join selection stability: `1.0`
- Count/count-distinct stability: `0.986`
- Paraphrase consistency score: `0.9907`
- Template dependency score: `0.1634`

## Failure Distribution

- `count_distinct_gap`: 7
- `join_reasoning_gap`: 55
- `no_sql_gap`: 844
- `none`: 1044
- `where_condition_gap`: 29

## Most Unstable Groups

- `example_002` [public_dev]: consistency `0.9167`, instability=answer_intent_changed, sql_shape_changed
- `gen_0007` [generated_prompt_diagnostic]: consistency `0.9167`, instability=answer_intent_changed, sql_shape_changed
- `gen_0008` [generated_prompt_diagnostic]: consistency `0.9167`, instability=answer_intent_changed, sql_shape_changed
- `gen_0009` [generated_prompt_diagnostic]: consistency `0.9167`, instability=answer_intent_changed, sql_shape_changed
- `example_014` [public_dev]: consistency `0.9286`, instability=table_changed, answer_intent_changed, sql_shape_changed
- `gen_0043` [generated_prompt_diagnostic]: consistency `0.9286`, instability=table_changed, answer_intent_changed, sql_shape_changed
- `gen_0044` [generated_prompt_diagnostic]: consistency `0.9286`, instability=table_changed, answer_intent_changed, sql_shape_changed
- `gen_0106` [generated_prompt_diagnostic]: consistency `0.9286`, instability=answer_intent_changed, sql_shape_changed
- `gen_0112` [generated_prompt_diagnostic]: consistency `0.9286`, instability=answer_intent_changed, sql_shape_changed
- `gen_0231` [generated_prompt_diagnostic]: consistency `0.9286`, instability=answer_intent_changed, sql_shape_changed
- `example_007` [public_dev]: consistency `0.9375`, instability=table_changed, count_changed, sql_shape_changed
- `gen_0022` [generated_prompt_diagnostic]: consistency `0.9375`, instability=table_changed, count_changed, sql_shape_changed
- `gen_0023` [generated_prompt_diagnostic]: consistency `0.9375`, instability=table_changed, count_changed, sql_shape_changed
- `gen_0024` [generated_prompt_diagnostic]: consistency `0.9375`, instability=table_changed, count_changed, sql_shape_changed
- `gen_0045` [generated_prompt_diagnostic]: consistency `0.9375`, instability=table_changed, answer_intent_changed, sql_shape_changed
- `gen_0142` [generated_prompt_diagnostic]: consistency `0.9444`, instability=route_changed, sql_shape_changed
- `gen_0200` [generated_prompt_diagnostic]: consistency `0.9444`, instability=route_changed, sql_shape_changed
- `gen_0111` [generated_prompt_diagnostic]: consistency `0.9524`, instability=route_changed, sql_shape_changed
- `gen_0205` [generated_prompt_diagnostic]: consistency `0.9524`, instability=route_changed, sql_shape_changed
- `gen_0247` [generated_prompt_diagnostic]: consistency `0.9524`, instability=route_changed, sql_shape_changed
