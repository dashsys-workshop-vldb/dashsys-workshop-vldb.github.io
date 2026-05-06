# Compact Context Measured Evaluation

This report is experimental and isolated. It does not update official SQL_FIRST_API_VERIFY scores, preferred strategy, submission metrics, or final submission artifacts.

- Shadow safety gate passed: True
- Feature flag: `ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE` (default: False; enabled for experiment: True)
- Packaged execution changed: False
- Official submission metrics updated: False
- Preferred strategy changed: False
- Rows: 28
- Avg score delta: -0.0
- Avg token delta: 4.2857
- Avg runtime delta: 0.0017
- Avg tool delta: 0.0
- Experimental measured efficiency improvement claimed: False
- Official measured efficiency improvement claimed: False

| Query ID | Current score | Compact score | Score delta | Token delta | Runtime delta | Tool delta | Answer changed? | Safe to enable? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `example_003` | 0.7156 | 0.7155 | -0.0001 | 4 | 0.0059 | 0 | False | False |
| `example_004` | 0.6744 | 0.6743 | -0.0001 | 4 | 0.0022 | 0 | False | False |
| `example_005` | 0.913 | 0.9129 | -0.0001 | 5 | 0.0028 | 0 | False | False |
| `example_006` | 0.7272 | 0.7271 | -0.0001 | 5 | 0.0049 | 0 | False | False |
| `example_007` | 0.6552 | 0.6552 | 0.0 | 4 | 0.0034 | 0 | False | False |
| `example_009` | 0.7576 | 0.7576 | 0.0 | 5 | 0.005 | 0 | False | False |
| `example_010` | 0.7898 | 0.7898 | 0.0 | 4 | 0.003 | 0 | False | False |
| `example_011` | 0.7455 | 0.7454 | -0.0001 | 5 | 0.0032 | 0 | False | False |
| `example_012` | 0.7287 | 0.7286 | -0.0001 | 5 | 0.0038 | 0 | False | False |
| `example_013` | 0.7149 | 0.7149 | 0.0 | 5 | 0.0036 | 0 | False | False |
| `example_015` | 0.6672 | 0.6672 | 0.0 | 3 | 0.0003 | 0 | False | False |
| `example_016` | 0.6621 | 0.662 | -0.0001 | 3 | 0.0006 | 0 | False | False |
| `example_017` | 0.5292 | 0.5292 | 0.0 | 4 | 0.0003 | 0 | False | False |
| `example_018` | 0.6654 | 0.6654 | 0.0 | 4 | -0.0001 | 0 | False | False |
| `example_019` | 0.5344 | 0.5344 | 0.0 | 4 | 0.0004 | 0 | False | False |
| `example_021` | 0.5394 | 0.5394 | 0.0 | 4 | 0.0006 | 0 | False | False |
| `example_022` | 0.5406 | 0.5405 | -0.0001 | 5 | 0.0014 | 0 | False | False |
| `example_023` | 0.5401 | 0.54 | -0.0001 | 5 | 0.0015 | 0 | False | False |
| `example_024` | 0.5361 | 0.5361 | 0.0 | 5 | 0.0012 | 0 | False | False |
| `example_025` | 0.5355 | 0.5354 | -0.0001 | 5 | 0.0012 | 0 | False | False |
| `example_026` | 0.5407 | 0.5407 | 0.0 | 5 | 0.0005 | 0 | False | False |
| `example_027` | 0.6017 | 0.6017 | 0.0 | 5 | 0.0001 | 0 | False | False |
| `example_028` | 0.5348 | 0.5348 | 0.0 | 4 | 0.001 | 0 | False | False |
| `example_029` | 0.5345 | 0.5345 | 0.0 | 3 | -0.0005 | 0 | False | False |
| `example_030` | 0.5308 | 0.5308 | 0.0 | 4 | -0.001 | 0 | False | False |
| `example_031` | 0.5339 | 0.5339 | 0.0 | 4 | 0.0003 | 0 | False | False |
| `example_032` | 0.6711 | 0.6711 | 0.0 | 4 | 0.001 | 0 | False | False |
| `example_034` | 0.6621 | 0.6621 | 0.0 | 3 | 0.0008 | 0 | False | False |

## Notes

- This is an isolated measured experiment; it does not update official eval results or submission metrics.
- Baseline rows are read from existing SQL_FIRST_API_VERIFY strict outputs.
- Compact-enabled runs write only under outputs/compact_context_measured_eval/<query_id>/compact_sql_first/.
- Measured efficiency improvement is experimental only and is not claimed for packaged SQL_FIRST_API_VERIFY.
