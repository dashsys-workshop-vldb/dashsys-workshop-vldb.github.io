# LLM Baseline Comparison

| System | Rows | Valid runs | Failed runs | Avg answer score on valid runs | Avg tool calls on valid runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAW_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 0 | 35 | 0.0000 | 0.00 |
| GUIDED_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 0 | 35 | 0.0000 | 0.00 |
| LLM_CONTROLLER_OPTIMIZED_AGENT | 35 | 35 | 0 | 0.4692 | 1.46 |

## Failed Real LLM Tool Loops

These rows are real LLM calls, but they are not counted as successful real tool-using baseline runs.

| Query ID | Tool calls executed? | Failure reason |
| --- | --- | --- |
| `example_000` | False | llm_request_failed |
| `example_000` | False | llm_request_failed |
| `example_001` | False | llm_request_failed |
| `example_001` | False | llm_request_failed |
| `example_002` | False | llm_request_failed |
| `example_002` | False | llm_request_failed |
| `example_003` | False | llm_request_failed |
| `example_003` | False | llm_request_failed |
| `example_004` | False | llm_request_failed |
| `example_004` | False | llm_request_failed |
| `example_005` | False | llm_request_failed |
| `example_005` | False | llm_request_failed |
| `example_006` | False | llm_request_failed |
| `example_006` | False | llm_request_failed |
| `example_007` | False | llm_request_failed |
| `example_007` | False | llm_request_failed |
| `example_008` | False | llm_request_failed |
| `example_008` | False | llm_request_failed |
| `example_009` | False | llm_request_failed |
| `example_009` | False | llm_request_failed |
