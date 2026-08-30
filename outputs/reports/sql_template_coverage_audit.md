# SQL Template Coverage Audit

Diagnostic-only audit of fixed SQL template coverage and schema-aware fallback opportunities.

- Rows: 285
- Template hits: 102
- Template misses: 183
- Existing fallback SQL used: 73
- Schema-aware candidate available on template misses: 183

## Likely Failures

- count_distinct_gap: 2
- join_reasoning_gap: 8
- no_sql_gap: 118
- none: 153
- where_condition_gap: 4

## Template Miss Examples

- `example_004` [public_dev]: none (candidate=schema_join_path)
- `example_015` [public_dev]: no_sql_gap (candidate=schema_count)
- `example_016` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_017` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_018` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_019` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_020` [public_dev]: no_sql_gap (candidate=schema_count)
- `example_022` [public_dev]: no_sql_gap (candidate=schema_count)
- `example_023` [public_dev]: no_sql_gap (candidate=schema_single_table)
- `example_024` [public_dev]: no_sql_gap (candidate=schema_single_table)
- `example_025` [public_dev]: no_sql_gap (candidate=schema_single_table)
- `example_026` [public_dev]: no_sql_gap (candidate=schema_count)
- `example_027` [public_dev]: no_sql_gap (candidate=schema_single_table)
- `example_028` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_029` [public_dev]: no_sql_gap (candidate=schema_count)
- `example_030` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_031` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_032` [public_dev]: no_sql_gap (candidate=schema_join_path)
- `example_034` [public_dev]: no_sql_gap (candidate=schema_count)
- `gen_0013` [generated_prompt_diagnostic]: none (candidate=schema_join_path)
