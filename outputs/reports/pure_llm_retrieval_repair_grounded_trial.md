# Pure LLM Retrieval Repair Grounded Trial

Diagnostic-only report. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## New Variants

- `retrieved_schema_sql_agent_v1`: status `unavailable`, strict `None`, SQL `None`, unsupported `None`
- `reviewed_sql_repair_agent_v1`: status `unavailable`, strict `None`, SQL `None`, unsupported `None`
- `execution_guided_sql_agent_v1`: status `unavailable`, strict `None`, SQL `None`, unsupported `None`
- `evidence_grounded_sql_agent_v1`: status `unavailable`, strict `None`, SQL `None`, unsupported `None`
- `full_retrieval_repair_grounded_pure_llm_v1`: status `unavailable`, strict `None`, SQL `None`, unsupported `None`

## Evaluation Status

- Executed new bounded LLM rows: `0`
- Bounded 10 run: `False`
- Full 35 run: `False`
- Skip reason: bounded 5-row hosted LLM gate unavailable; configured backend failed or timed out, so bounded 10 and full 35 were not allowed

## SQL Zero Root Cause

- Dominant category: `no_sql_called_when_needed`
- Cause: SQL score is primarily zero because the agent did not call execute_sql when SQL evidence was needed.

## Hosted LLM Attempts

- `python3 scripts/run_pure_llm_tool_agent_eval.py --stabilization-set --variant full_retrieval_repair_grounded_pure_llm_v1` -> `backend_probe_failed_401_no_new_llm_rows`
- `LLM_PROVIDER=openai python3 scripts/run_pure_llm_tool_agent_eval.py --stabilization-set --variant full_retrieval_repair_grounded_pure_llm_v1` -> `stopped_after_exceeding_diagnostic_bound_no_report_output`
- `python3 scripts/run_pure_llm_tool_agent_eval.py --artifact-only --limit 5 --variant retrieved_schema_sql_agent_v1 --variant reviewed_sql_repair_agent_v1 --variant execution_guided_sql_agent_v1 --variant evidence_grounded_sql_agent_v1 --variant full_retrieval_repair_grounded_pure_llm_v1` -> `artifact_only_report_written_new_llm_rows_0`
