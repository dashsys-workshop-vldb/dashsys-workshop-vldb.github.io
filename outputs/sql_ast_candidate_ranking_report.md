# SQL AST Candidate Ranking Report

- Candidate count: 15
- Avg AST quality score: 0.9538
- Unknown schema count: 2

| Query ID | Candidate | Parsed | Tables | Unknowns | Joins | Aggs | Filters | Quality |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `example_000` | executed_sql | True | dim_campaign |  | 0 | 0 | 0 | 0.98 |
| `example_001` | executed_sql | True | dim_campaign |  | 0 | 0 | 1 | 0.98 |
| `example_002` | executed_sql | True | dim_campaign |  | 0 | 0 | 0 | 1.0 |
| `example_003` | executed_sql | True | dim_segment, hkg_br_segment_target, dim_target |  | 2 | 0 | 1 | 0.9 |
| `example_004` | executed_sql | True | dim_target |  | 0 | 0 | 1 | 0.98 |
| `example_005` | executed_sql | True | dim_target |  | 0 | 0 | 0 | 0.98 |
| `example_006` | executed_sql | True | dim_collection, hkg_br_blueprint_collection, dim_blueprint |  | 2 | 4 | 1 | 1.0 |
| `example_007` | executed_sql | True | hkg_br_blueprint_collection, dim_collection, dim_blueprint |  | 2 | 0 | 1 | 0.9 |
| `example_008` | executed_sql | True | hkg_br_segment_property, dim_segment |  | 1 | 0 | 1 | 0.98 |
| `example_009` | executed_sql | True | dim_blueprint, hkg_br_blueprint_collection, hkg_br_blueprint_property |  | 2 | 4 | 1 | 0.98 |
| `example_010` | executed_sql | True | dim_blueprint |  | 0 | 2 | 1 | 1.0 |
| `example_011` | executed_sql | True | dim_blueprint |  | 0 | 2 | 0 | 1.0 |
| `example_012` | executed_sql | True | dim_segment, hkg_br_segment_target, dim_target | MONTH | 2 | 0 | 1 | 0.8967 |
| `example_013` | executed_sql | True | dim_collection | DAY | 0 | 0 | 1 | 0.73 |
| `example_014` | executed_sql | True | dim_collection |  | 0 | 0 | 1 | 1.0 |
