# NL-to-SQL Paraphrase Consistency

Diagnostic-only report. Generated prompt variants are coverage stress tests, not official score evidence.

- Semantic groups: `285`
- Paraphrase consistency score: `0.9907`
- Route stability: `0.9825`
- Table selection stability: `0.9719`
- Join selection stability: `1.0`
- Count/count-distinct stability: `0.986`
- Answer intent stability: `0.9544`

## Instability Counts

- `answer_intent_changed`: 13
- `count_changed`: 4
- `route_changed`: 5
- `sql_shape_changed`: 69
- `table_changed`: 8

## Representative Unstable Groups

- `example_002`: `0.9167` (answer_intent_changed, sql_shape_changed)
- `gen_0007`: `0.9167` (answer_intent_changed, sql_shape_changed)
- `gen_0008`: `0.9167` (answer_intent_changed, sql_shape_changed)
- `gen_0009`: `0.9167` (answer_intent_changed, sql_shape_changed)
- `example_014`: `0.9286` (table_changed, answer_intent_changed, sql_shape_changed)
- `gen_0043`: `0.9286` (table_changed, answer_intent_changed, sql_shape_changed)
- `gen_0044`: `0.9286` (table_changed, answer_intent_changed, sql_shape_changed)
- `gen_0106`: `0.9286` (answer_intent_changed, sql_shape_changed)
- `gen_0112`: `0.9286` (answer_intent_changed, sql_shape_changed)
- `gen_0231`: `0.9286` (answer_intent_changed, sql_shape_changed)
- `example_007`: `0.9375` (table_changed, count_changed, sql_shape_changed)
- `gen_0022`: `0.9375` (table_changed, count_changed, sql_shape_changed)
- `gen_0023`: `0.9375` (table_changed, count_changed, sql_shape_changed)
- `gen_0024`: `0.9375` (table_changed, count_changed, sql_shape_changed)
- `gen_0045`: `0.9375` (table_changed, answer_intent_changed, sql_shape_changed)
- `gen_0142`: `0.9444` (route_changed, sql_shape_changed)
- `gen_0200`: `0.9444` (route_changed, sql_shape_changed)
- `gen_0111`: `0.9524` (route_changed, sql_shape_changed)
- `gen_0205`: `0.9524` (route_changed, sql_shape_changed)
- `gen_0247`: `0.9524` (route_changed, sql_shape_changed)
