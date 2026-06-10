# Implementation Notes For VLDB-Style System Paper

## System Thesis

The system uses deterministic control around a small constrained planning surface. The model is not trusted to invent schema joins or API endpoints. Instead, code performs schema indexing, endpoint cataloging, route classification, metadata selection, validation, execution, and trajectory logging.

## Components

- Local data layer: DuckDB views over all DBSnapshot parquet files, with read-only SQL enforcement and row-limit protection.
- Schema layer: automatic table/column inspection, ID-like column detection, bridge-table detection, join-graph construction, and curated join hints when expected DASHSys entity tables are present.
- API layer: compact Adobe endpoint catalog covering journey/campaign, audience/segment, flow service, catalog dataset, and schema registry APIs.
- Routing layer: deterministic keyword rules for route type and domain type.
- Metadata layer: per-query compact context containing selected tables, columns, join hints, endpoint candidates, constraints, and answer policy.
- Strategy layer: multiple comparable strategies from SQL-only baseline through SQL-first/API-verify.
- Validation layer: SQL table/column/read-only checks and API endpoint/path-param checks.
- Logging layer: metadata, filled prompt, trajectory, compact result previews, tool counts, runtime, token estimates, and redacted headers.
- Evaluation layer: public-example runner with SQL/API/answer scoring and efficiency-aware final score.

## Strategies

- `SQL_ONLY_BASELINE`: minimal tool use, efficient but incomplete for live platform-state questions.
- `LLM_FREE_AGENT_BASELINE`: broad-context deterministic stand-in for a freer agent, useful as an inefficiency baseline.
- `DETERMINISTIC_ROUTER_SELECTED_METADATA`: compact metadata plus route-selected tools.
- `SQL_FIRST_API_VERIFY`: SQL grounds names/IDs first, API verifies live/platform state when needed.
- `TEMPLATE_FIRST`: reusable query patterns before falling back to SQL-first/API-verify; strong on known examples but monitored for overfitting risk.

## Reproducibility

All inputs are local files or environment variables. Outputs are deterministic JSON/CSV/Markdown artifacts. Missing official data produces explicit empty reports rather than fabricated numbers.

## Expected Paper Evaluation

Report correctness by SQL/API/final answer dimensions, then efficiency by tool calls, runtime, token estimates, and preprocessing/context-selection time. Use `outputs/strategy_comparison.md` for the headline table once public examples are available.
