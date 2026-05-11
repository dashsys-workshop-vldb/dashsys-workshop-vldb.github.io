# LLM Baseline Comparison

| System | Rows | Valid runs | Failed runs | Avg answer score on valid runs | Avg tool calls on valid runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAW_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 34 | 1 | 0.4182 | 1.44 |
| GUIDED_REAL_LLM_TWO_TOOLS_BASELINE | 35 | 35 | 0 | 0.4076 | 1.46 |
| LLM_CONTROLLER_OPTIMIZED_AGENT | 35 | 35 | 0 | 0.4471 | 1.46 |

## Failed Real LLM Tool Loops

These rows are real LLM calls, but they are not counted as successful real tool-using baseline runs.

| Query ID | Tool calls executed? | Failure reason |
| --- | --- | --- |
| `example_014` | False | no_valid_tool_calls_executed |
