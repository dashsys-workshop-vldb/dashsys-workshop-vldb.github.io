# DASHSys Agent System

This project builds a DASHSys Systems Track agent for natural-language question answering over a local DuckDB/parquet snapshot and Adobe REST APIs.

The default deterministic strategy is `SQL_FIRST_API_VERIFY`. The newer LLM layer is optional: when an OpenAI or OpenRouter key is available, a real LLM can help with prompt routing, final response writing, and NL-to-SQL experiments. When no key is available, all LLM modes skip or fall back safely and the deterministic backend still works.

## 1. What the System Does

The system answers questions using two official data tools:

- `execute_sql(sql)` over local DuckDB/parquet data
- `call_api(method, url, params, headers)` for Adobe API requests

The full data path is:

```text
User query
-> Prompt Router
-> query normalization and token extraction
-> candidate/full schema context selection
-> QueryAnalysis and metadata selection
-> SQL/API planning or optional LLM NL-to-SQL
-> validation and optional repair/fallback
-> SQL/API execution
-> EvidenceBus forwarding
-> answer slots and claim verification
-> final answer
-> trajectory JSON with checkpoints
```

The project hardcodes routing policy, not final answers. Templates and LLM SQL are both validated before execution.

## 2. Setup

Use Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Place data at:

```text
data/data.json
data/DBSnapshot/*.parquet
```

Optional path overrides:

```bash
export DASHAGENT_DATA_JSON=/path/to/data.json
export DASHAGENT_DBSNAPSHOT_DIR=/path/to/DBSnapshot
export DASHAGENT_OUTPUTS_DIR=/path/to/outputs
export DASHAGENT_PROMPTS_DIR=/path/to/prompts
```

## 3. Credentials

Adobe credentials are optional for local/public evaluation. Missing credentials put API calls in dry-run mode.

```bash
export CLIENT_ID=...
export CLIENT_SECRET=...
export IMS_ORG=...
export SANDBOX=...
export ACCESS_TOKEN=...
export ADOBE_BASE_URL=https://platform.adobe.io
```

Real LLM integration is also optional. OpenAI remains the default provider:

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
```

OpenRouter is also supported through its OpenAI-compatible chat completions API:

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="..."
export OPENROUTER_MODEL="openai/gpt-4o-mini"
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

OpenRouter support is optional. Not all OpenRouter models support native tool/function calling; for the real two-tool baselines, use a model with reliable tool calling.

No credentials are required for tests. Secrets are redacted from trajectories and reports.

## 4. Prompt Routing Policy

The first decision is whether the prompt needs evidence:

| Prompt | Route | Why |
| --- | --- | --- |
| Explain how checkpoints work | `LLM_DIRECT` | conceptual, no DB/API evidence needed |
| List all journeys | `LOCAL_DB_ONLY` | local snapshot is enough |
| Is the 'Birthday Message' journey published? | `SQL_PLUS_API` | SQL grounds the journey, API can verify live state |
| How many merge policies are configured? | `API_ONLY` | merge policies are an API/platform family |
| What overall pattern do you see? | data pipeline if ambiguous | avoids unsupported facts |

The router lives in `dashagent/prompt_router.py` and records `checkpoint_00_prompt_router`.

## 5. Real LLM Integration

Main modes:

- Deterministic backend: no LLM key required; uses `SQL_FIRST_API_VERIFY`.
- Optimized LLM controller: LLM routes or calls the optimized backend tool, then writes a grounded final answer.
- Raw real LLM baseline: `RAW_REAL_LLM_TWO_TOOLS_BASELINE`; the LLM only gets `execute_sql` and `call_api` with minimal affordance.
- Guided real LLM baseline: `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE`; the same two tools plus schema/API affordance, endpoint repair, validation feedback, and guardrails.
- Backward-compatible baseline: `REAL_LLM_TWO_TOOLS_BASELINE` remains an alias for the raw baseline concept.
- LLM SQL strategies: LLM can generate SQL from candidate or full schema context, then validation/repair/fallback runs before execution.

Commands:

```bash
python3 scripts/run_llm_query.py "Explain how checkpoints work" --mode optimized
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode deterministic
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode baseline
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode guided-baseline
python3 scripts/run_llm_query.py "List all journeys" --mode baseline --provider openrouter
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode guided-baseline --provider openrouter
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode candidate-sql
python3 scripts/run_llm_query.py "Is the 'Birthday Message' journey published?" --mode full-schema-sql
python3 scripts/run_llm_baseline_eval.py
```

If the selected provider key is missing, real LLM modes report `skipped` or fall back to `SQL_FIRST_API_VERIFY`.

## 6. LLM NL-To-SQL

Optional strategies:

- `CANDIDATE_GUIDED_LLM_SQL`
- `FULL_SCHEMA_LLM_SQL`
- `LLM_SQL_FIRST_API_VERIFY`

Candidate context is retrieval only. It narrows likely tables, columns, joins, and APIs, but it does not decide the final SQL or answer. Adaptive context policy records one of `candidate`, `expanded_candidate`, `hybrid`, or `full_schema`. If confidence is low, margin is zero, or validation fails, the system expands context and then falls back to deterministic `SQL_FIRST_API_VERIFY`.

Run an optional LLM strategy:

```bash
python3 scripts/run_dev_eval.py --strategies LLM_SQL_FIRST_API_VERIFY
python3 scripts/run_dev_eval.py --strict --strategies LLM_SQL_FIRST_API_VERIFY
```

Without an LLM key, these strategies still complete by using the deterministic fallback.

## 7. Candidate Context Report

Generate a report showing that schema context selection is retrieval, not public-example hardcoding:

```bash
python3 scripts/generate_candidate_context_report.py
```

Outputs:

- `outputs/candidate_context_report.md`
- `outputs/candidate_context_report.json`

The report includes candidate context token size, full-schema token size, compression ratio, recall@k when gold SQL/API exists, candidate miss analysis, recommended context mode, and a curated join-hint audit. Gold is used only for report recall, not for candidate selection.

## 8. Strict Evaluation

Normal evaluation keeps backward-compatible scoring:

```bash
python3 scripts/run_dev_eval.py
```

Strict evaluation audits score inflation:

```bash
python3 scripts/run_dev_eval.py --strict
```

Strict mode writes:

- `outputs/eval_results_strict.json`
- `outputs/eval_results_strict.csv`
- `outputs/strategy_comparison_strict.md`

In strict mode, missing gold SQL/API/answer fields are unscored, not treated as free `1.0`.

## 9. Baseline Comparison

Compare naive LLM/tool behavior against the optimized system:

```bash
python3 scripts/run_dev_eval.py
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_llm_baseline_eval.py
python3 scripts/generate_baseline_comparison_report.py
```

Outputs:

- `outputs/baseline_comparison_report.md`
- `outputs/baseline_comparison_report.json`
- `outputs/llm_baseline_comparison.md`

The real LLM baselines are marked skipped when the selected provider key is unavailable. Reports keep raw and guided baselines separate, separate failed tool loops from successful ones, and include tool execution vs evidence availability fields. Dry-run API calls count as tool invocations, but they do not count as live evidence when Adobe credentials are unavailable.

## 10. Visualize Prompt-To-Answer Data Flow

Run one query:

```bash
python3 scripts/run_one_query.py "Is the 'Birthday Message' journey published?" --strategy SQL_FIRST_API_VERIFY
```

Then generate dataflow artifacts:

```bash
python3 scripts/generate_dataflow_visualization.py outputs/is_the_birthday_message_journey_published/sql_first_api_verify/trajectory.json
```

Outputs:

- `outputs/demo_dataflow/dataflow.mmd`
- `outputs/demo_dataflow/dataflow.md`
- `outputs/demo_dataflow/dataflow.html`

The visualization shows prompt routing, normalized query, tokens/entities, selected tables/APIs, SQL/API calls, validation, execution results, EvidenceBus, answer slots, verification, and final answer.

## 11. OpenAI Trace Export

Export real trajectory checkpoints as optional OpenAI Agents SDK spans:

```bash
python3 scripts/export_trajectory_to_openai_trace.py outputs/is_the_birthday_message_journey_published/sql_first_api_verify/trajectory.json --trace-name dashsys-full-query-checkpoints
```

If the SDK or `OPENAI_API_KEY` is missing, the command no-ops safely and prints a warning.

## 12. Core Repository Layout

- `dashagent/db.py`: read-only DuckDB/parquet execution.
- `dashagent/schema_index.py`: schema summary and join hints.
- `dashagent/endpoint_catalog.py`: allowed Adobe endpoints.
- `dashagent/prompt_router.py`: `LLM_DIRECT`, `LOCAL_DB_ONLY`, `SQL_PLUS_API`, `API_ONLY` routing.
- `dashagent/candidate_context_builder.py`: candidate/full schema context retrieval.
- `dashagent/llm_client.py`, `dashagent/llm_sql_generator.py`, `dashagent/llm_tool_agent.py`: optional real LLM paths.
- `dashagent/query_normalizer.py`, `dashagent/query_tokens.py`, `dashagent/relevance_scorer.py`: lightweight NLP helpers.
- `dashagent/query_analysis.py`, `dashagent/metadata_selector.py`, `dashagent/planner.py`: deterministic planning path.
- `dashagent/evidence_policy.py`, `dashagent/call_budget.py`, `dashagent/plan_optimizer.py`: efficiency controls.
- `dashagent/evidence_bus.py`, `dashagent/answer_slots.py`, `dashagent/answer_verifier.py`, `dashagent/answer_reranker.py`: evidence and answer verification.
- `dashagent/checkpoints.py`, `dashagent/dataflow_visualizer.py`, `dashagent/agents_sdk_adapter.py`: traceability and visualization.
- `dashagent/executor.py`: main per-query execution path.
- `dashagent/eval_harness.py`: normal and strict evaluation.

## 13. Run One Query

```bash
python3 scripts/run_one_query.py "Is the 'Birthday Message' journey published?" --strategy SQL_FIRST_API_VERIFY
```

Per-query outputs:

```text
outputs/<query_id>/<strategy>/
  metadata.json
  filled_system_prompt.txt
  trajectory.json
```

## 14. Diagnostic Reports

```bash
python3 scripts/generate_failure_analysis.py
python3 scripts/generate_family_score_report.py
python3 scripts/generate_pareto_report.py
python3 scripts/generate_template_generalization_report.py
python3 scripts/generate_checkpoint_report.py
python3 scripts/generate_candidate_context_report.py
python3 scripts/generate_baseline_comparison_report.py
```

Generated reports under `outputs/` are useful project evidence and should remain readable.

## 15. Tests And Packaging

Run tests:

```bash
python3 -m pytest
```

Package source and query outputs:

```bash
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

`package_query_outputs.py` defaults to `SQL_FIRST_API_VERIFY`.

## 16. Recommended Full Pipeline

```bash
python3 scripts/warm_cache.py
python3 scripts/inspect_schema.py
python3 scripts/run_dev_eval.py
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_llm_baseline_eval.py
python3 scripts/generate_candidate_context_report.py
python3 scripts/generate_baseline_comparison_report.py
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

## 17. Safety Rules

- Keep `SQL_FIRST_API_VERIFY` as the deterministic default.
- Do not hard-code public-example answers, exact public query strings, or hidden-test assumptions.
- Keep SQL read-only; validators block destructive statements.
- API calls must match the endpoint catalog unless explicit fallback mode is enabled.
- Never commit credentials or generated secrets.
- Do not remove checkpoint logging, validation, secret redaction, packaging, or readiness checks.
