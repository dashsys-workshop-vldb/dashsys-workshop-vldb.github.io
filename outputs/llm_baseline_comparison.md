# LLM Baseline Comparison

| System | Rows | Valid runs | Failed runs | Avg answer score on valid runs | Avg tool calls on valid runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAW_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 27 | 8 | 0.4210 | 1.63 |
| GUIDED_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 26 | 9 | 0.4223 | 1.62 |
| LLM_CONTROLLER_OPTIMIZED_AGENT | 35 | 35 | 0 | 0.4601 | 1.46 |

## Failed Real LLM Tool Loops

These rows are real LLM calls, but they are not counted as successful real tool-using baseline runs.

| Query ID | Tool calls executed? | Failure reason |
| --- | --- | --- |
| `example_026` | False | llm_request_failed |
| `example_027` | False | llm_request_failed |
| `example_027` | False | llm_request_failed |
| `example_028` | False | llm_request_failed |
| `example_028` | False | llm_request_failed |
| `example_029` | False | llm_request_failed |
| `example_029` | False | llm_request_failed |
| `example_030` | False | llm_request_failed |
| `example_030` | False | llm_request_failed |
| `example_031` | False | llm_request_failed |
| `example_031` | False | llm_request_failed |
| `example_032` | False | llm_request_failed |
| `example_032` | False | llm_request_failed |
| `example_033` | False | llm_request_failed |
| `example_033` | False | llm_request_failed |
| `example_034` | False | llm_request_failed |
| `example_034` | False | llm_request_failed |
