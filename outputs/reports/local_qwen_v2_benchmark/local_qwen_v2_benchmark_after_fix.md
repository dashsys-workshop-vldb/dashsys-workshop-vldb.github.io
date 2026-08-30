# Local Qwen V2 Benchmark After Targeted Fixes

## Objective Metrics
| Metric | Value |
|---|---:|
| V2 completed | true |
| Baseline completed | true |
| query_count | 35 |
| timeout_count | 1 |
| failed_query_ids | example_003 |
| compiled_sql_count | 19 |
| compiled_api_count | 22 |
| V2 SQL calls | 23 |
| V2 API calls | 23 |
| V2 tool calls | 46 |
| runtime_fact_count | 50 |
| unsupported_claims | 5 |
| no_tool_fp | 0 |
| final_semantic_gate_failures | 10 |
| local/live scope errors | 0 |
| API_ERROR no-data misuse | 0 |
| raw SQL fallback used count | 0 |
| semantic alias count | 0 |
| exact cache hits | 0 |

## Score Comparison
| Metric | SQL_FIRST_API_VERIFY | ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 | V2 - SQL_FIRST |
|---|---:|---:|---:|
| Final | 0.6562 | 0.1912 | -0.4650 |
| Correctness | 0.6812 | 0.2520 | -0.4292 |
| Answer | 0.3223 | 0.1774 | -0.1449 |
| SQL | 0.9333 | 0.0000 | -0.9333 |
| API | 0.9791 | 0.4263 | -0.5528 |
| Tool calls | 1.4571 | 1.3143 | -0.1428 |
| Runtime sec | 0.0246 | 16.5385 | 16.5139 |
| Estimated tokens | 796.8571 | 2062.3429 | 1265.4858 |

## Conclusion
The local Qwen SDK-toolcall V2 path passes focused smoke but remains a shadow-only research path. It is not safe to promote because strict dev eval has one timeout, 10 final semantic gate failures, and large score regressions versus `SQL_FIRST_API_VERIFY`.
