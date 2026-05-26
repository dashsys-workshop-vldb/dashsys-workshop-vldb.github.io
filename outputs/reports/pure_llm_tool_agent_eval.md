# Pure LLM Tool Agent Eval

Diagnostic-only report. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

- New LLM calls executed: `True`
- Promotion allowed: `False`
- Best variant: `LLM_CONTROLLER_OPTIMIZED_AGENT`

## Systems

| System | Rows | Strict | SQL | API | Answer | Unsupported claims |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 0.2244 | 0.12 | 0.4287 | 0.2631 | 2 |
| `LLM_CONTROLLER_OPTIMIZED_AGENT` | 35 | 0.6328 | 0.9333 | 0.9791 | 0.2615 | 0 |
| `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | 35 | 0.1596 | 0.0 | 0.3397 | 0.2337 | 1 |
| `conservative_sql_first_multi_candidate_v1` | 5 | -0.0177 | 0.0 | 0.0 | 0.2375 | 0 |
