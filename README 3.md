# DASHSys Agent System

This project builds a DASHSys Systems Track agent for natural-language question answering over a local DuckDB/parquet snapshot and Adobe REST APIs.

The LLM is the high-level controller. The optimized backend provides SQL/API planning, validation, execution, answer verification, and checkpointed trajectory logging. The default final-submission strategy is `SQL_FIRST_API_VERIFY`.

## 1. What the System Does

The agent answers questions using only the two official tool types:

- `execute_sql(sql)` over the local DuckDB/parquet database
- `call_api(method, url, params, headers)` for Adobe API requests

The main data flow is:

```text
User query
-> simple prompt gate
-> query normalization/token extraction
-> relevance scoring and QueryAnalysis
-> metadata/context selection
-> SQL/API planning
-> evidence policy and call budget
-> validation
-> SQL/API execution
-> EvidenceBus forwarding
-> answer slots and claim verification
-> final answer
-> trajectory JSON with checkpoints
```

In simple terms, the system first decides whether the question needs data. For data questions, it chooses the relevant tables and APIs, builds a safe plan, validates it, runs only the needed tools, extracts evidence, verifies the final answer, and writes a reproducible trace.

## 2. Repository Layout

Core backend modules:

- `dashagent/db.py`: read-only DuckDB/parquet loading and SQL execution.
- `dashagent/schema_index.py`: schema summaries, ID detection, bridge detection, and join hints.
- `dashagent/endpoint_catalog.py`: allowed Adobe endpoint catalog.
- `dashagent/router.py`: deterministic query routing.
- `dashagent/query_normalizer.py`, `dashagent/query_tokens.py`, `dashagent/relevance_scorer.py`: lightweight NLP helpers.
- `dashagent/query_analysis.py`: one-pass shared query analysis.
- `dashagent/sql_templates.py`, `dashagent/api_templates.py`, `dashagent/answer_templates.py`: reusable SQL/API/answer templates.
- `dashagent/evidence_policy.py`, `dashagent/call_budget.py`, `dashagent/plan_optimizer.py`, `dashagent/plan_ensemble.py`: efficiency and safety controls.
- `dashagent/evidence_bus.py`: forwards structured SQL/API evidence.
- `dashagent/answer_slots.py`, `dashagent/answer_claims.py`, `dashagent/answer_verifier.py`, `dashagent/answer_reranker.py`: verification-first answer layer.
- `dashagent/checkpoints.py`, `dashagent/agent_tools.py`, `dashagent/simple_prompt_gate.py`: LLM-agent-compatible checkpoint and wrapper layer.
- `dashagent/executor.py`: main per-query execution path.
- `dashagent/eval_harness.py`: public-example evaluation.

Important scripts:

- `scripts/warm_cache.py`: precompute reusable schema/API/gold-pattern caches.
- `scripts/inspect_schema.py`: inspect DBSnapshot parquet files and write schema reports.
- `scripts/run_one_query.py`: run a single query.
- `scripts/run_dev_eval.py`: run public-example evaluation across strategies.
- `scripts/generate_failure_analysis.py`: rank low-scoring examples.
- `scripts/generate_family_score_report.py`: group results by query family.
- `scripts/generate_pareto_report.py`: compare correctness and efficiency tradeoffs.
- `scripts/generate_template_generalization_report.py`: check overfitting risk.
- `scripts/generate_checkpoint_report.py`: summarize checkpoint coverage and data flow.
- `scripts/package_submission.py`: create `outputs/source_code.zip`.
- `scripts/package_query_outputs.py`: create final per-query output folders.
- `scripts/check_submission_ready.py`: verify packaging, JSON validity, secrets, placeholders, and default strategy.

## 3. Setup

Use Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

If you prefer not to use a virtual environment, install the same requirements in your active Python environment.

## 4. Data Placement

Place the official DASHSys data here:

```text
data/data.json
data/DBSnapshot/*.parquet
```

These files are intentionally ignored by git because they are external data artifacts.

You can override paths with environment variables:

```bash
export DASHAGENT_DATA_JSON=/path/to/data.json
export DASHAGENT_DBSNAPSHOT_DIR=/path/to/DBSnapshot
export DASHAGENT_OUTPUTS_DIR=/path/to/outputs
export DASHAGENT_PROMPTS_DIR=/path/to/prompts
```

Do not hard-code machine-local paths in source code.

## 5. Adobe Credentials And Dry-Run Mode

Adobe credentials must come only from environment variables:

```bash
export CLIENT_ID=...
export CLIENT_SECRET=...
export IMS_ORG=...
export SANDBOX=...
export ACCESS_TOKEN=...
export ADOBE_BASE_URL=https://platform.adobe.io
```

Never commit credentials. The code redacts secret-looking values in trajectories and packaging checks.

Missing credentials are expected during local/public evaluation. In that case, API calls run in dry-run mode. Dry-run validates the planned method, endpoint, params, and call order, but it does not prove live Adobe API behavior.

## 6. Warm Cache And Inspect Schema

Run cache warmup before a full evaluation or final package:

```bash
python3 scripts/warm_cache.py
```

Then inspect the local schema:

```bash
python3 scripts/inspect_schema.py
```

These commands write reusable artifacts such as:

- `outputs/schema_summary.json`
- `outputs/join_graph.json`
- `outputs/endpoint_catalog.json`
- `outputs/gold_sql_patterns.json`
- `outputs/gold_api_patterns.json`
- `outputs/gold_answer_patterns.json`

The cache is reused when DBSnapshot parquet file names/mtimes and `data/data.json` mtime are unchanged.

## 7. Run One Query

Example:

```bash
python3 scripts/run_one_query.py "Is the 'Birthday Message' journey published?" --strategy SQL_FIRST_API_VERIFY
```

Per-query outputs are written under:

```text
outputs/<query_id>/<strategy>/
  metadata.json
  filled_system_prompt.txt
  trajectory.json
```

Every trajectory includes:

- the original query
- selected strategy
- route/domain information
- checkpointed data flow
- validation results
- SQL/API tool calls
- answer diagnostics
- final answer
- tool-call count, runtime, and estimated tokens

## 8. Run Development Evaluation

Run all strategies on the public examples:

```bash
python3 scripts/run_dev_eval.py
```

Strategies evaluated:

- `SQL_ONLY_BASELINE`
- `LLM_FREE_AGENT_BASELINE`
- `DETERMINISTIC_ROUTER_SELECTED_METADATA`
- `SQL_FIRST_API_VERIFY`
- `TEMPLATE_FIRST`

Primary outputs:

- `outputs/eval_results.json`
- `outputs/eval_results.csv`
- `outputs/strategy_comparison.md`

The expected default and recommended final-submission strategy is `SQL_FIRST_API_VERIFY`.

## 9. Generate Diagnostic Reports

After evaluation, generate the diagnostic reports:

```bash
python3 scripts/generate_failure_analysis.py
python3 scripts/generate_family_score_report.py
python3 scripts/generate_pareto_report.py
python3 scripts/generate_template_generalization_report.py
python3 scripts/generate_checkpoint_report.py
```

Important generated reports:

- `outputs/failure_analysis.md`
- `outputs/family_score_report.md`
- `outputs/pareto_report.md`
- `outputs/template_generalization_check.md`
- `outputs/checkpoint_report.md`

These reports are intentionally not broadly gitignored. Future agents and GPT runs need to inspect them.

## 10. Checkpointed Agent Layer

The checkpoint layer makes the optimized backend easier to inspect from an LLM-agent harness such as Claude Agent SDK or OpenAI Agents SDK.

Each full data query records checkpoints such as:

- raw query capture
- query normalization
- token/entity extraction
- relevance scoring
- QueryAnalysis
- lookup path prediction
- compact context card
- candidate plan selection
- plan optimization
- evidence policy
- call budget
- validation
- tool execution
- EvidenceBus forwarding
- answer slots
- answer verification
- answer reranking
- final answer

High-level LLM-facing wrappers are available in `dashagent/agent_tools.py`:

- `analyze_query_tool(query)`
- `plan_data_answer_tool(query)`
- `run_data_answer_tool(query)`
- `verify_answer_tool(query, answer, evidence)`

The optional `dashagent/agents_sdk_adapter.py` exports checkpoints as custom spans when the OpenAI Agents SDK is installed. If the SDK is absent, it no-ops safely.

## 11. Run Tests

Run the test suite:

```bash
python3 -m pytest
```

The tests cover database loading, validators, routing, metadata selection, templates, efficiency policy, NLP helpers, answer verification, checkpoint logging, packaging helpers, and readiness behavior.

## 12. Package The Submission

First package source code:

```bash
python3 scripts/package_submission.py
```

This writes:

```text
outputs/source_code/
outputs/source_code.zip
```

Then package per-query outputs:

```bash
python3 scripts/package_query_outputs.py
```

This writes:

```text
outputs/final_submission/
outputs/final_submission_manifest.json
```

By default, `package_query_outputs.py` selects `SQL_FIRST_API_VERIFY` when multiple strategy outputs exist for the same query.

To override for experiments only:

```bash
export DASHAGENT_SUBMISSION_STRATEGY=TEMPLATE_FIRST
```

Do not override the final-submission strategy unless evaluation and the user explicitly approve it.

## 13. Readiness Check

Run:

```bash
python3 scripts/check_submission_ready.py
```

The checker verifies:

- `outputs/source_code.zip` exists
- `prompts/system_prompt_template.txt` exists
- final submission query folders contain `metadata.json`, `filled_system_prompt.txt`, and `trajectory.json`
- JSON files parse
- trajectory files contain required fields
- no obvious secrets are present
- no unresolved API path placeholders remain
- unresolved API params are explicitly warned
- default strategy is `SQL_FIRST_API_VERIFY`
- generated diagnostic reports exist

## 14. Recommended Full Pipeline

Use this before handing off final work:

```bash
python3 scripts/warm_cache.py
python3 scripts/inspect_schema.py
python3 scripts/run_dev_eval.py
python3 scripts/generate_failure_analysis.py
python3 scripts/generate_family_score_report.py
python3 scripts/generate_pareto_report.py
python3 scripts/generate_template_generalization_report.py
python3 scripts/generate_checkpoint_report.py
python3 -m pytest
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

For optional robustness and threshold diagnostics:

```bash
python3 scripts/tune_thresholds.py
python3 scripts/run_robustness_eval.py
```

## 15. Safety Rules

SQL is read-only. The SQL validator blocks destructive or environment-changing statements such as:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `CREATE`
- `COPY`
- `ATTACH`
- `DETACH`

API calls must match the endpoint catalog unless explicit fallback mode is enabled. Avoid unresolved placeholders such as `{schema_id}` or `<destination_id>`; when possible, forward IDs from SQL evidence through `EvidenceBus`.

## 16. Cleanup Rules

Do not commit local machine artifacts:

- `.DS_Store`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.ipynb_checkpoints/`
- editor swap/temp/backup files

`outputs/source_code.zip` should not include those files. Re-run `python3 scripts/package_submission.py` after cleanup to rebuild the zip.

Generated top-level reports under `outputs/` are useful project evidence and should remain readable unless the user asks to remove them.

## 17. Current Development Principle

Keep the project deterministic-first:

- Do not rewrite the architecture.
- Do not add multi-agent complexity.
- Do not hard-code public-example answers or exact public query strings.
- Do not remove checkpoint logging.
- Do not weaken validation, secret redaction, or packaging checks.
- Do not increase tool calls unless evaluation proves it is necessary.
- Keep `SQL_FIRST_API_VERIFY` as the default strategy.
