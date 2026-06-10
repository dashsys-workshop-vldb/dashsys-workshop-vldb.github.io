# DASHSys 2026 QA Agent

This repository implements a reproducible, deterministic-first agent for the DASHSys 2026 Real-World Systems Track / Competition. It answers natural-language questions using only:

- `execute_sql(sql)` over a local DuckDB database backed by parquet files
- `call_api(method, url, params, headers)` against Adobe REST APIs

The design intentionally avoids a large multi-agent system. Code controls schema selection, endpoint selection, validation, trajectory logging, and evaluation. The LLM-facing prompt is compact and constrained.

## Setup

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If your machine does not provide `python` on PATH, use `python3` for the commands below.

## Data Placement

The official data is not committed to this repository. Place it here:

```text
data/data.json
data/DBSnapshot/*.parquet
```

You may override those locations without hard-coding paths:

```bash
export DASHAGENT_DATA_JSON=/path/to/data.json
export DASHAGENT_DBSNAPSHOT_DIR=/path/to/DBSnapshot
export DASHAGENT_OUTPUTS_DIR=/path/to/outputs
```

## Adobe Environment Variables

Credentials are read only from the environment:

```bash
export CLIENT_ID=...
export CLIENT_SECRET=...
export IMS_ORG=...
export SANDBOX=...
export ACCESS_TOKEN=...          # optional
export ADOBE_BASE_URL=https://platform.adobe.io
```

Never commit credentials. If credentials are missing, API calls run in dry-run mode and trajectories record that no live API evidence was available.

## Inspect Schema

```bash
python scripts/inspect_schema.py
```

This writes:

- `outputs/schema_summary.json`
- `outputs/join_graph.json`
- `outputs/endpoint_catalog.json`
- `outputs/gold_api_patterns.json` when `data/data.json` is available

For a final run, warm the reusable cache first:

```bash
python scripts/warm_cache.py
```

This precomputes schema summaries, join graphs, endpoint catalog output, and mined public-example patterns. Query execution loads the cache when the DBSnapshot file names/mtimes and `data/data.json` mtime are unchanged.

## Run One Query

```bash
python scripts/run_one_query.py "Is the 'Birthday Message' journey published?" --strategy SQL_FIRST_API_VERIFY
```

Per-query outputs are written under `outputs/<query_id>/<strategy>/`:

- `metadata.json`
- `filled_system_prompt.txt`
- `trajectory.json`

## Run Dev Evaluation

```bash
python scripts/run_dev_eval.py
```

This evaluates all implemented strategies on `data/data.json`:

- `SQL_ONLY_BASELINE`
- `LLM_FREE_AGENT_BASELINE`
- `DETERMINISTIC_ROUTER_SELECTED_METADATA`
- `SQL_FIRST_API_VERIFY`
- `TEMPLATE_FIRST`

Evaluation outputs:

- `outputs/eval_results.json`
- `outputs/eval_results.csv`
- `outputs/strategy_comparison.md`

Additional diagnostic reports:

```bash
python scripts/generate_failure_analysis.py
python scripts/generate_family_score_report.py
python scripts/generate_pareto_report.py
python scripts/generate_template_generalization_report.py
```

The combined score is:

```text
correctness_score = 0.4 * sql_score + 0.3 * api_score + 0.3 * answer_score
final_score = correctness_score - 0.1 * efficiency_penalty
```

## Interpret Strategy Comparison

Open `outputs/strategy_comparison.md`. It reports average correctness, final score, tool calls, runtime, estimated tokens, and automatic recommendations:

- best correctness
- best efficiency
- best overall
- next components to improve

If no examples are present, the report says so honestly instead of fabricating results.

## Package Submission

```bash
python scripts/package_submission.py
```

This verifies required source files, scans for obvious credential leaks, and writes:

- `outputs/source_code/`
- `outputs/source_code.zip`

To package per-query outputs for a final submission after running queries or dev eval:

```bash
python scripts/package_query_outputs.py
```

By default this selects `SQL_FIRST_API_VERIFY` when multiple strategy outputs exist for the same query. Override with:

```bash
export DASHAGENT_SUBMISSION_STRATEGY=TEMPLATE_FIRST
```

This writes:

- `outputs/final_submission/`
- `outputs/final_submission_manifest.json`

## Architecture Notes

The main execution path is:

1. `DuckDBDatabase` loads every parquet file in `data/DBSnapshot` as a read-only DuckDB view.
2. `SchemaIndex` inspects tables/columns, detects ID-like columns and bridge tables, and creates join hints.
3. `EndpointCatalog` exposes a compact, curated Adobe endpoint list and extracts reusable patterns from public gold API examples when available.
4. `QueryRouter` classifies route type and domain using deterministic keyword rules.
5. `MetadataSelector` emits compact per-query metadata instead of full schema/API context.
6. `StrategyPlanner` creates constrained SQL/API plans for each strategy.
7. `SQLValidator` and `APIValidator` block hallucinated or unsafe tool calls.
8. `AgentExecutor` executes validated calls and writes `metadata.json`, `filled_system_prompt.txt`, and `trajectory.json`.
9. `EvalHarness` compares generated SQL/API/final answers against public examples and reports correctness/efficiency.

## Security

- SQL execution blocks write or environment-changing statements.
- API credentials are never stored in source files.
- Trajectories redact secret-looking headers and environment values.
- Missing credentials trigger dry-run API mode.

## Tests

```bash
pytest
```

The tests create a tiny temporary parquet snapshot and verify DB loading, SQL/API validation, routing, metadata selection, trajectory redaction, and the evaluation harness.
