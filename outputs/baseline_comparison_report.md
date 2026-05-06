# Baseline Comparison Report

## Summary Table

| System | Description | Normal correctness | Strict correctness | Final score | Tool calls | Tokens | Runtime | LLM status |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| RAW_REAL_LLM_TWO_TOOLS_BASELINE | Raw real LLM with execute_sql/call_api only | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | 1.2571 | 1318.3429 | 4.8366 | mixed_valid_and_failed_tool_agent_runs |
| GUIDED_REAL_LLM_TWO_TOOLS_BASELINE | Guided real LLM with execute_sql/call_api plus schema/API affordances | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | 1.2 | 2057.3429 | 3.625 | mixed_valid_and_failed_tool_agent_runs |
| REAL_LLM_TWO_TOOLS_BASELINE | Backward-compatible alias for the raw real LLM baseline | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | n/a - tool-loop diagnostic baseline | n/a | n/a | n/a | not_run |
| LLM_FREE_AGENT_BASELINE | Deterministic approximation of a broad LLM agent | 0.6707 | 0.4879 | 0.4529 | 2.1143 | 1018.6 | 0.0187 | n/a |
| SQL_ONLY_BASELINE | Local DB only | 0.5763 | 0.2983 | 0.2795 | 1.0 | 751.1143 | 0.0126 | n/a |
| SQL_FIRST_API_VERIFY | Current deterministic optimized backend | 0.8407 | 0.6743 | 0.6486 | 1.4571 | 894.4286 | 0.0112 | n/a |
| CANDIDATE_GUIDED_LLM_SQL | Optional candidate-context LLM SQL with fallback | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| FULL_SCHEMA_LLM_SQL | Optional full-schema LLM SQL with fallback | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| LLM_SQL_FIRST_API_VERIFY | Optional LLM SQL plus deterministic API verification | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| LLM_CONTROLLER_OPTIMIZED_AGENT | Optional LLM controller with optimized backend tool | n/a | n/a | n/a | n/a | n/a | n/a | valid_tool_agent_run |

Note: RAW/GUIDED real LLM rows are diagnostic tool-loop baselines. They show tool-use reliability and efficiency, while `SQL_FIRST_API_VERIFY` remains the packaged scoring strategy.

## Raw vs Guided Real LLM Tool Loops

| Variant | Rows | Successful | Failed | Valid run rate | Tool execution success rate | Avg valid tool calls | Avg invalid tool calls | Avg endpoint repairs | Avg schema hints |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw | 35 | 27 | 8 | 0.7714 | 0.7714 | 1.6296 | 0.3143 | 0.0 | 0.0 |
| Guided | 35 | 26 | 9 | 0.7429 | 0.7429 | 1.6154 | 0.0286 | 0.6286 | 0.0286 |

## Tool Execution vs Evidence Availability

A dry-run API call means the tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing. Dry-run API calls are not counted as successful live evidence.

| Variant | Dry-run only API calls | Avg successful evidence count | Avg invalid tool calls |
| --- | ---: | ---: | ---: |
| Raw | 15 | 0.3714 | 0.3143 |
| Guided | 24 | 0.2857 | 0.0286 |

## Provider Reliability Note

Some OpenRouter/OpenAI-backed baseline rows may fail at request level. These rows are separated under failed real LLM tool loops, are not counted as successful tool-loop runs, and do not affect the packaged `SQL_FIRST_API_VERIFY` submission.

| Variant | `llm_request_failed` count |
| --- | ---: |
| Raw | 8 |
| Guided | 9 |

## Tool Failure Categories

| Category | Raw | Guided |
| --- | ---: | ---: |
| dry_run_only_api_count | 15 | 24 |
| duplicate_invalid_call_count | 0 | 0 |
| max_turns_exceeded_count | 0 | 0 |
| no_final_answer_count | 8 | 9 |
| schema_introspection_failure_count | 4 | 1 |
| unknown_column_count | 1 | 1 |
| unknown_endpoint_count | 0 | 0 |
| unknown_table_count | 9 | 0 |
| unsupported_negative_answer_count | 4 | 0 |

## Token And Runtime Efficiency

| Variant | Avg prompt/context tokens | Avg runtime | Avg tool calls |
| --- | ---: | ---: | ---: |
| Raw | 1318.3429 | 4.8366 | 1.2571 |
| Guided | 2057.3429 | 3.625 | 1.2 |

## Successful Real LLM Tool Loops

| Variant | Query ID | Tool calls | Tool calls executed? | Valid run? | Evidence count | Dry-run only? | Invalid calls | Endpoint repairs |
| --- | --- | ---: | --- | --- | ---: | --- | ---: | ---: |
| Raw | `example_000` | 2 | True | True | 0 | True | 0 | 0 |
| Guided | `example_000` | 2 | True | True | 1 | True | 0 | 1 |
| Raw | `example_001` | 2 | True | True | 0 | False | 1 | 0 |
| Guided | `example_001` | 1 | True | True | 0 | False | 0 | 0 |
| Raw | `example_002` | 1 | True | True | 1 | False | 0 | 0 |
| Guided | `example_002` | 1 | True | True | 1 | False | 0 | 0 |
| Raw | `example_003` | 1 | True | True | 0 | True | 0 | 0 |
| Guided | `example_003` | 2 | True | True | 0 | True | 0 | 2 |
| Raw | `example_004` | 3 | True | True | 1 | True | 1 | 0 |
| Guided | `example_004` | 2 | True | True | 0 | True | 0 | 1 |
| Raw | `example_005` | 1 | True | True | 0 | True | 0 | 0 |
| Guided | `example_005` | 1 | True | True | 0 | True | 0 | 1 |
| Raw | `example_006` | 2 | True | True | 0 | True | 1 | 0 |
| Guided | `example_006` | 1 | True | True | 0 | True | 0 | 0 |
| Raw | `example_007` | 2 | True | True | 0 | True | 1 | 0 |
| Guided | `example_007` | 1 | True | True | 0 | True | 0 | 1 |
| Raw | `example_008` | 1 | True | True | 0 | False | 0 | 0 |
| Guided | `example_008` | 1 | True | True | 0 | False | 0 | 0 |
| Raw | `example_009` | 3 | True | True | 0 | False | 2 | 0 |
| Guided | `example_009` | 1 | True | True | 1 | False | 0 | 0 |

## Failed Real LLM Tool Loops

Some real LLM calls did not complete valid tool-using runs.

These rows are not treated as successful real tool-using baseline runs.

| Variant | Query ID | Tool calls | Tool calls executed? | Failure reason |
| --- | --- | ---: | --- | --- |
| Guided | `example_026` | 0 | False | llm_request_failed |
| Raw | `example_027` | 0 | False | llm_request_failed |
| Guided | `example_027` | 0 | False | llm_request_failed |
| Raw | `example_028` | 0 | False | llm_request_failed |
| Guided | `example_028` | 0 | False | llm_request_failed |
| Raw | `example_029` | 0 | False | llm_request_failed |
| Guided | `example_029` | 0 | False | llm_request_failed |
| Raw | `example_030` | 0 | False | llm_request_failed |
| Guided | `example_030` | 0 | False | llm_request_failed |
| Raw | `example_031` | 0 | False | llm_request_failed |
| Guided | `example_031` | 0 | False | llm_request_failed |
| Raw | `example_032` | 0 | False | llm_request_failed |
| Guided | `example_032` | 0 | False | llm_request_failed |
| Raw | `example_033` | 0 | False | llm_request_failed |
| Guided | `example_033` | 0 | False | llm_request_failed |
| Raw | `example_034` | 0 | False | llm_request_failed |
| Guided | `example_034` | 0 | False | llm_request_failed |

## Improvement: Optimized vs Naive

| Metric | Naive | Optimized | Absolute gain | Relative gain |
| --- | ---: | ---: | ---: | ---: |
| SQL correctness | 0.06 | 0.9333 | 0.8733 | 14.555 |
| API correctness | 0.9742 | 0.9791 | 0.0049 | 0.005 |
| answer correctness | 0.245 | 0.3076 | 0.0626 | 0.2555 |
| overall correctness | 0.4879 | 0.6743 | 0.1864 | 0.382 |
| final score | 0.4529 | 0.6486 | 0.1957 | 0.4321 |
| tool calls | 2.1143 | 1.4571 | -0.6572 | -0.3108 |
| tokens | 1018.6 | 894.4286 | -124.1714 | -0.1219 |
| runtime | 0.0187 | 0.0112 | -0.0075 | -0.4011 |

## Technique Contribution

| Technique | Active in naive baseline? | Active in optimized system? | Expected effect |
| --- | --- | --- | --- |
| prompt router | False | True | keeps conceptual prompts out of the data pipeline and routes evidence prompts safely |
| query normalization | False | True | improves correctness, efficiency, or observability in the optimized path |
| token extraction | False | True | improves correctness, efficiency, or observability in the optimized path |
| candidate context retrieval | False | True | narrows schema/API context without deciding final SQL |
| full-schema fallback | False | True | prevents retrieval misses from blocking NL-to-SQL |
| LLM NL-to-SQL | True | True | lets a real model generate SQL when credentials exist |
| SQL/API templates | False | True | improves correctness, efficiency, or observability in the optimized path |
| plan optimizer | False | True | improves correctness, efficiency, or observability in the optimized path |
| evidence policy | False | True | improves correctness, efficiency, or observability in the optimized path |
| call budget | False | True | improves correctness, efficiency, or observability in the optimized path |
| EvidenceBus | False | True | forwards exact SQL/API evidence into later steps |
| answer verifier | False | True | blocks unsupported final-answer claims |
| answer reranker | False | True | improves correctness, efficiency, or observability in the optimized path |
| checkpoint visualization | False | True | improves correctness, efficiency, or observability in the optimized path |
| OpenAI trace export | False | True | improves correctness, efficiency, or observability in the optimized path |

## System Comparison Diagram

```mermaid
flowchart LR
  A[User Prompt] --> B[Naive LLM]
  B --> C[execute_sql / call_api]
  C --> D[Final Answer]
  A --> E[Prompt Router]
  E --> F[Candidate/Full Schema Context]
  F --> G[LLM NL-to-SQL or SQL_FIRST fallback]
  G --> H[Validation / Repair]
  H --> I[execute_sql / call_api]
  I --> J[EvidenceBus]
  J --> K[Answer Verification]
  K --> L[Final Answer + Checkpoints + Dataflow + Trace]
```

## Lowest Failure Deltas

| Query ID | Naive final | Optimized final | Delta | Likely reason |
| --- | ---: | ---: | ---: | --- |
| `example_004` | 0.8355 | 0.835 | -0.0005 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_020` | 0.7878 | 0.8008 | 0.013 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_022` | 0.8014 | 0.8144 | 0.013 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_026` | 0.7979 | 0.8109 | 0.013 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_015` | 0.7947 | 0.8078 | 0.0131 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_034` | 0.7969 | 0.81 | 0.0131 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_029` | 0.7811 | 0.7945 | 0.0134 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_017` | 0.7897 | 0.8032 | 0.0135 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_027` | 0.7953 | 0.8088 | 0.0135 | optimized path uses validated templates/evidence policy/checkpoints |
| `example_033` | 0.7838 | 0.7973 | 0.0135 | optimized path uses validated templates/evidence policy/checkpoints |
