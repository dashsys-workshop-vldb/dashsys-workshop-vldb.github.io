# Tool Calling Compiled Policy Candidate

- Policy id: `tcp_04f92b35aa59`
- Recommendation: `promote_candidate`
- Runtime policy already matches candidate: `True`

## Deterministic Rules
- If route is SQL-answerable and API is optional while structured live_success_count=0, expose execute_sql only.
- If route is API_ONLY or API_REQUIRED, keep call_api available; never strip required API evidence.
- If exactly one SDK tool is exposed, set parallel_tool_calls=false where the provider SDK supports it.
- Use compact tool schemas and compact evidence summaries; preserve row count, key fields, API state, and caveats.
- If backend answer is complete and verifier passes, skip LLM rewrite instead of spending another SDK turn.
