# V2 Failure Triage: Local Qwen SDK-Toolcall Run

## Summary
Fresh six-prompt smoke passed, so strict dev eval was allowed. The strict V2 run completed 35 rows under a 240s per-query timeout, but `example_003` timed out and V2 still trails `SQL_FIRST_API_VERIFY` substantially.

## Fresh Smoke Gate
| Metric | Value |
|---|---:|
| passed_count | 7 |
| row_count | 7 |
| timeout_count | 0 |
| unsupported_claims | 0 |
| no_tool_fp | 0 |
| final_semantic_gate_final_failures | 0 |
| compiled_sql_count | 5 |
| compiled_api_count | 1 |
| runtime_fact_count | 8 |
| raw_sql_fallback_used_count | 0 |

## Strict Dev Eval Comparison
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

## V2 Strict Diagnostics
| Metric | Value |
|---|---:|
| query_count | 35 |
| timeout_count | 1 |
| timeout_query_ids | example_003 |
| failed_query_ids | example_003 |
| sdk_toolcall_semantic_ir_used_count | 32 |
| atomic_protocol_fallback_used_count | 2 |
| compiled_sql_count | 19 |
| compiled_api_count | 22 |
| SQL calls | 23 |
| API calls | 23 |
| tool calls | 46 |
| runtime_fact_count | 50 |
| unsupported_claims | 5 |
| no_tool_fp | 0 |
| final_semantic_gate_initial_failures | 15 |
| final_semantic_gate_final_failures | 10 |
| local_live_scope_errors | 0 |
| API_ERROR no-data misuse | 0 |
| raw_sql_fallback_used_count | 0 |
| semantic_alias_count | 0 |
| exact_cache_hits | 0 |

Timeout trajectories are excluded from trajectory-level diagnostic counts because a timed-out child can leave stale or partial output files.

## Rows With Semantic Gate Issues
| query_id | SQL | API | facts | initial_gate_failures | final_gate_failures | unsupported_claims |
|---|---:|---:|---:|---:|---:|---:|
| example_001 | 2 | 2 | 5 | 1 | 1 | 0 |
| example_005 | 1 | 0 | 1 | 1 | 1 | 1 |
| example_006 | 1 | 0 | 1 | 1 | 0 | 0 |
| example_007 | 1 | 0 | 1 | 1 | 1 | 0 |
| example_008 | 1 | 1 | 3 | 1 | 0 | 0 |
| example_010 | 1 | 0 | 1 | 1 | 0 | 1 |
| example_012 | 3 | 1 | 4 | 1 | 1 | 1 |
| example_017 | 0 | 2 | 2 | 1 | 1 | 0 |
| example_018 | 0 | 1 | 1 | 1 | 1 | 0 |
| example_021 | 1 | 1 | 2 | 1 | 1 | 0 |
| example_024 | 1 | 0 | 1 | 1 | 1 | 0 |
| example_027 | 0 | 1 | 1 | 1 | 1 | 0 |
| example_030 | 1 | 0 | 1 | 1 | 0 | 1 |
| example_033 | 1 | 1 | 2 | 1 | 1 | 0 |
| example_034 | 1 | 2 | 3 | 1 | 0 | 1 |

## Root Cause Assessment
- Smoke path is now stable and verifies SDK toolcall Semantic IR, local evidence selection, and final answer gating on the focused prompts.
- Strict dev eval still has one execution stability failure: `example_003` timed out at dependency resolution.
- Strict dev eval still has answer-grounding failures: 10 final semantic gate failures and 5 unsupported-claim observations across non-timeout trajectories.
- V2 reduces average tool calls versus SQL_FIRST, but score regressions are too large to justify promotion.
- Packaged default remains `SQL_FIRST_API_VERIFY`.
