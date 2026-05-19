# Core Tool Optimization Audit

- Generated at: 2026-05-19T02:44:21.704691+00:00
- Packaged strategy: `SQL_FIRST_API_VERIFY`
- Strict score baseline: 0.6553
- Hidden-style: 48/48
- Final submission ready: True
- Live success count: 0
- Diagnostic only: True
- Official organizer-weighted score claim: False

## execute_sql

- Correctness role: grounds SQL-answerable prompts in local DuckDB/parquet evidence
- Efficiency role: dominates local evidence latency, validation cost, and SQL result preview size
- Current bottlenecks:
  - repeated validation of repaired or normalized equivalent SQL
  - raw result previews can carry unused fields for count/status/date prompts
  - validation and execution summaries are not explicitly optimized by intent
- Optimization candidates: SQL-1, SQL-2, SQL-3, SQL-4, SQL-5

## call_api

- Correctness role: captures Adobe API state/evidence when local SQL is insufficient or API evidence is required
- Efficiency role: controls network/dry-run calls, API caveat size, and endpoint validation overhead
- Current bottlenecks:
  - optional API dry-run attempts can add caveat noise when SQL already answers
  - identical API attempts can be repeated within one query if planner emits duplicates
  - raw error bodies must be compressed before answer/report context
- Optimization candidates: API-1, API-2, API-3, API-4, API-5, API-6

## Safety

- SQL read-only validation remains required.
- Adobe data API calls remain GET-only.
- Endpoint catalog paths are unchanged.
- No final submission artifacts are written by this audit.
