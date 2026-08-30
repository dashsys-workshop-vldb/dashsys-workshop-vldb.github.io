# Official Token Reduction Packaged Trial

This is an isolated packaged flag trial, not a packaged submission change.

- Feature flag default: False
- Protected official output hashes unchanged: True
- Packaged execution changed: False
- Recommendation: `safe_to_make_packaged_default_in_future`

## Summary

- Total rows: 35
- Safe rows: 35
- Unsafe rows: 0
- Avg score delta: 0.0006
- Avg token delta: -67.7714
- Avg runtime delta: 0.0005
- Avg tool delta: 0.0
- Runtime budget: {'acceptable_noise_threshold_seconds': 0.005, 'avg_runtime_delta': 0.0005, 'avg_runtime_budget_ok': True, 'row_runtime_regression_over_20pct_count': 0, 'runtime_budget_ok': True, 'runtime_regression_query_ids': []}

| Query ID | Score delta | Token delta | Runtime delta | Runtime >20%? | Tool delta | Answer changed? | SQL changed? | API changed? | Safe? | Rejection reason |
| --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |
| `example_000` | 0.0002 | -35 | 0.0022 | False | 0 | False | False | False | True |  |
| `example_001` | 0.0007 | -90 | 0.0004 | False | 0 | False | False | False | True |  |
| `example_002` | 0.0005 | -64 | 0.0006 | False | 0 | False | False | False | True |  |
| `example_003` | 0.0005 | -67 | 0.0018 | False | 0 | False | False | False | True |  |
| `example_004` | 0.0002 | -24 | -0.0 | False | 0 | False | False | False | True |  |
| `example_005` | 0.0004 | -46 | 0.0002 | False | 0 | False | False | False | True |  |
| `example_006` | 0.0007 | -81 | 0.0025 | True | 0 | False | False | False | True |  |
| `example_007` | 0.0008 | -91 | 0.0008 | False | 0 | False | False | False | True |  |
| `example_008` | 0.0003 | -32 | 0.002 | False | 0 | False | False | False | True |  |
| `example_009` | 0.0006 | -70 | 0.0029 | True | 0 | False | False | False | True |  |
| `example_010` | 0.0006 | -72 | 0.0014 | False | 0 | False | False | False | True |  |
| `example_011` | 0.0007 | -81 | 0.001 | False | 0 | False | False | False | True |  |
| `example_012` | 0.0006 | -72 | 0.0015 | False | 0 | False | False | False | True |  |
| `example_013` | 0.0018 | -219 | 0.0022 | False | 0 | False | False | False | True |  |
| `example_014` | 0.0007 | -79 | 0.0008 | False | 0 | False | False | False | True |  |
| `example_015` | 0.0003 | -26 | 0.0007 | False | 0 | False | False | False | True |  |
| `example_016` | 0.0006 | -80 | -0.0003 | False | 0 | False | False | False | True |  |
| `example_017` | 0.0007 | -80 | -0.0004 | False | 0 | False | False | False | True |  |
| `example_018` | 0.0007 | -80 | -0.0001 | False | 0 | False | False | False | True |  |
| `example_019` | 0.0007 | -80 | -0.0 | False | 0 | False | False | False | True |  |
| `example_020` | 0.0002 | -26 | -0.0003 | False | 0 | False | False | False | True |  |
| `example_021` | 0.0006 | -73 | 0.0 | False | 0 | False | False | False | True |  |
| `example_022` | 0.0004 | -58 | 0.0002 | False | 0 | False | False | False | True |  |
| `example_023` | 0.0005 | -58 | 0.0002 | False | 0 | False | False | False | True |  |
| `example_024` | 0.0005 | -58 | -0.0005 | False | 0 | False | False | False | True |  |
| `example_025` | 0.0005 | -58 | 0.0006 | False | 0 | False | False | False | True |  |
| `example_026` | 0.0005 | -58 | -0.0002 | False | 0 | False | False | False | True |  |
| `example_027` | 0.0005 | -59 | 0.0 | False | 0 | False | False | False | True |  |
| `example_028` | 0.0007 | -81 | -0.0003 | False | 0 | False | False | False | True |  |
| `example_029` | 0.0002 | -27 | 0.0001 | False | 0 | False | False | False | True |  |
| `example_030` | 0.0007 | -81 | -0.0001 | False | 0 | False | False | False | True |  |
| `example_031` | 0.0007 | -81 | 0.0006 | False | 0 | False | False | False | True |  |
| `example_032` | 0.0006 | -73 | -0.0003 | False | 0 | False | False | False | True |  |
| `example_033` | 0.0007 | -84 | -0.0008 | False | 0 | False | False | False | True |  |
| `example_034` | 0.0002 | -28 | -0.0003 | False | 0 | False | False | False | True |  |
