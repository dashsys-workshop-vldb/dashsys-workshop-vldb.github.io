# AGENTS.md

Guidance for coding agents working on this DASHSys 2026 Systems Track repository.

## Project Purpose

This repo implements a deterministic-first natural-language QA agent for the DASHSys 2026 Real-World Systems Track. The submitted system must answer questions using only:

- `execute_sql(sql)` over local DuckDB/parquet data
- `call_api(method, url, params, headers)` against Adobe REST APIs

For each query, the system must generate:

- `metadata.json`
- `filled_system_prompt.txt`
- `trajectory.json`

The default final-submission strategy is `SQL_FIRST_API_VERIFY`. Do not change that default unless evaluation clearly proves a better general strategy and the user explicitly agrees.

## Architecture Rules

- Do not rewrite the architecture.
- Do not add multi-agent complexity.
- Prefer deterministic code over LLM guessing.
- Keep the LLM-facing prompt compact and constrained.
- Never hard-code public-example answers or exact public query strings.
- Reusable templates are allowed only when schema/API validated and generalizable.
- Execute exactly one selected plan per query. Do not execute multiple candidate plans.
- Preserve validation, secret redaction, trajectory logging, and reproducibility.

Main execution path:

1. `DuckDBDatabase` loads parquet files as read-only DuckDB views.
2. `SchemaIndex` builds schema summaries, ID detection, bridge detection, and join hints.
3. `EndpointCatalog` defines allowed Adobe API endpoints.
4. `QueryRouter`, `QueryAnalysis`, NLP helpers, lookup paths, and context cards select compact context.
5. `MetadataSelector` writes per-query metadata.
6. `StrategyPlanner` creates constrained SQL/API steps.
7. `PlanOptimizer` and `plan_ensemble` dedupe, budget, and select one plan before execution.
8. `SQLValidator` and `APIValidator` validate tool calls.
9. `AgentExecutor` executes validated calls and writes outputs.
10. `EvalHarness` scores correctness and efficiency.

## Important Files

- `dashagent/db.py`: DuckDB/parquet loading and safe SQL execution.
- `dashagent/schema_index.py`: schema summaries and join graph.
- `dashagent/endpoint_catalog.py`: allowed Adobe endpoint catalog.
- `dashagent/router.py`: deterministic query routing.
- `dashagent/query_normalizer.py`, `dashagent/query_tokens.py`, `dashagent/relevance_scorer.py`: lightweight NLP selection helpers.
- `dashagent/query_analysis.py`: one-pass query analysis.
- `dashagent/sql_templates.py`, `dashagent/api_templates.py`, `dashagent/answer_templates.py`: reusable templates.
- `dashagent/evidence_policy.py`, `dashagent/call_budget.py`, `dashagent/plan_optimizer.py`, `dashagent/plan_ensemble.py`: efficiency and safety controls.
- `dashagent/executor.py`: main per-query execution path.
- `dashagent/eval_harness.py`: public-example evaluation.
- `scripts/run_dev_eval.py`: run all strategies on public examples.
- `scripts/package_submission.py`, `scripts/package_query_outputs.py`, `scripts/check_submission_ready.py`: final packaging and readiness.

## Data And Credentials

Expected local data placement:

```text
data/data.json
data/DBSnapshot/*.parquet
```

Do not hard-code absolute paths. Use `Config` and environment overrides:

- `DASHAGENT_DATA_JSON`
- `DASHAGENT_DBSNAPSHOT_DIR`
- `DASHAGENT_OUTPUTS_DIR`
- `DASHAGENT_PROMPTS_DIR`

Adobe credentials must come only from environment variables:

- `ADOBE_ACCESS_TOKEN`
- `ADOBE_API_KEY`
- `ADOBE_ORG_ID`
- `ADOBE_SANDBOX_NAME`
- `ADOBE_CLIENT_ID`
- `ADOBE_CLIENT_SECRET`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `IMS_ORG`
- `SANDBOX`
- `ACCESS_TOKEN`
- `ADOBE_BASE_URL`

Never print, log, commit, or package secrets. Access tokens, API keys, and client secrets must be fully redacted; org ID and sandbox name are masked by default. Missing credentials are expected; dry-run API mode is valid and must be reported honestly in answers and trajectories.

## Live Adobe API Readiness

Live Adobe API readiness is infrastructure validation, not score promotion. Assume Adobe API will eventually be connected, so do not optimize away required API behavior just because local credentials are missing. `API_REQUIRED` remains required in live mode, `API_OPTIONAL` can run when policy selects it, and dry-run is only a safe local fallback.

Use:

```bash
python3 scripts/audit_live_adobe_api_readiness.py
python3 scripts/generate_api_required_readiness_matrix.py
python3 scripts/run_live_api_readiness_smoke.py
python3 scripts/run_live_api_evidence_pipeline_trial.py
python3 scripts/run_mock_live_api_evidence_pipeline_trial.py
```

Live smoke/trials are GET-only by default, must not call endpoints with unresolved path parameters unless a safe prior GET discovery step supplied the ID, and must never overwrite `outputs/eval/`, `outputs/eval_results_strict.json`, `outputs/final_submission/`, or `outputs/final_submission_manifest.json`. Live readiness reports are not official scoring artifacts, and no live API evidence may be fabricated.

## Live Adobe API Evidence Pipeline

The future target is real Adobe API evidence, not dry-run optimization. Response parsing should populate `parsed_evidence` with endpoint metadata, evidence state, parser mode, IDs, names, statuses, counts, timestamps, errors, pagination, and redacted previews. EvidenceBus and answer slots must keep live API evidence, dry-run unavailable, empty live results, malformed responses, and API errors distinct.

Discovery chains are GET-only and must never guess IDs. Any discovered path parameter must record provenance (`id_source`, `source_endpoint`, `source_field`, `source_query_id_or_fixture`). Mock fixtures in `tests/fixtures/adobe_api_responses/` use synthetic data to validate endpoint-family parsers and discovery readiness before credentials arrive.

## System-Wide SDK-Based LLM Rule

All LLM/model calls must go through `dashagent.llm_client.get_llm_client()` or the shared `LLMClient` abstraction. OpenAI-compatible providers must use the OpenAI SDK, Anthropic providers must use the Anthropic SDK, and model/provider switching must be controlled by `.env.local` or environment variables rather than code changes.

Do not use raw `requests`, `curl`, direct `/chat/completions`, hand-built provider HTTP calls, or provider-specific direct HTTP wrappers for LLM runtime testing, baselines, diagnostics, prompt-suite runs, answer rewrite search, candidate search, NL-to-SQL strategies, controller agents, or report generation. This SDK rule applies only to LLM/model provider calls; Adobe REST API execution remains on the existing Adobe API client/tool path.

Run `python3 scripts/generate_sdk_usage_audit.py` after LLM-related changes. The report at `outputs/reports/sdk_usage_audit.md/json` must show `runtime_llm_direct_http_hits = 0`.

## LLM Semantic Routing Helper

`dashagent/semantic_routing_helper.py` is optional routing-hint infrastructure for low-confidence or ambiguous prompts. It is default-off (`ENABLE_LLM_SEMANTIC_ROUTER=false`) and shadow-only by default (`LLM_SEMANTIC_ROUTER_SHADOW_ONLY=true`).

The helper must use `get_llm_client()` only, return structured routing hints only, validate all hints against known routes/domains/intents/tables/API families, and never generate final answers, fabricate SQL/API evidence, execute tools, or bypass validators. Non-shadow behavior is isolated-trial only and must not be used by packaging scripts unless a later explicit strict/safety promotion approves it.

Run `python3 scripts/run_llm_semantic_router_shadow_eval.py --limit 50` for the diagnostic report at `outputs/reports/llm_semantic_router_shadow_eval.md/json`.

## Diagnostic Prompt Suite

`scripts/generate_diagnostic_prompt_suite.py` creates `data/generated_prompt_suite.json/md` from `data/data.json` for broad coverage testing. Stable source IDs are assigned by order as `example_001`, `example_002`, and so on when source rows lack IDs.

`scripts/run_diagnostic_prompt_suite.py` runs generated prompts through `SQL_FIRST_API_VERIFY` as diagnostic coverage only. The default runner limit is 50 prompts; use `--full` to run all prompts, `--clean` to remove only `outputs/diagnostic_prompt_suite/`, and `--with-llm-semantic-router-shadow` to include routing-helper shadow stats.

Generated prompts are diagnostic-only, `should_be_scored=false`, not official benchmark data, not runtime hints, and not packaged into final submission.

## Decision-Stage Feedback Loops

Every serious improvement candidate must start from a workflow decision-stage question, then proceed through hypothesis, baseline, isolated trial, failure analysis, 3-5 controlled variants, and an evidence-backed decision. Do not treat one failed isolated run as proof that a whole idea is impossible; say the variant failed, explain why, then test the next controlled variant when the candidate remains plausible.

Use `python3 scripts/run_workflow_decision_audit.py` to produce `outputs/reports/workflow_decision_map.md/json` and `outputs/reports/workflow_decision_audit.md/json`. Use `python3 scripts/run_decision_feedback_loop.py` for isolated feedback-loop reports such as `outputs/reports/improvement_feedback_loop_index.md/json` and `outputs/reports/feedback_loop_semantic_router_final.md/json`.

Generated diagnostic prompts are coverage-only and cannot support official strict-score improvement or promotion claims. If a variant improves a clear subcategory without total strict-score improvement and without safety regression, label it `locally_useful_but_not_promotable`. For answer-only variants, the trial fails if SQL hash, API hash, tool count, selected evidence hash, or dry-run label changes. Do not mix multiple behavior-changing candidate families in the same diff unless each family has its own isolated flag and report.

## Evidence-Aware Answer Synthesis

Evidence-aware answer synthesis is deterministic and answer-only. It may audit final-answer use of SQL/API evidence, generate isolated rewrite candidates, and run faithfulness checks, but it must not rerun SQL/API, change validators, or alter packaged `SQL_FIRST_API_VERIFY` behavior.

Use:

```bash
python3 scripts/run_evidence_usage_audit.py
python3 scripts/run_evidence_aware_answer_rewrite_trial.py
python3 scripts/run_sql_evidence_usage_audit.py
python3 scripts/run_confidence_calibration_audit.py
python3 scripts/run_token_efficiency_audit.py
```

Answer-only trials must preserve SQL hash, API hash, tool count, route, plan, selected evidence hash, and dry-run label hash. The selected evidence hash covers normalized SQL result facts, parsed API evidence, EvidenceBus fields, answer slots, evidence states, and dry-run labels while excluding runtime timestamps, durations, and debug-only metadata. Faithfulness rejection focuses on factual drift only: wrong counts, names, statuses, dates, unsupported availability claims, or fabricated SQL/API evidence. If `API_REQUIRED` and dry-run unavailable, keep a short live-API-unavailable caveat.

## Development Workflow

Before major changes, record the current baseline if the user asks for an optimization pass:

```bash
python3 scripts/warm_cache.py
python3 scripts/inspect_schema.py
python3 scripts/run_dev_eval.py
python3 scripts/generate_failure_analysis.py
python3 scripts/generate_family_score_report.py
python3 scripts/generate_pareto_report.py
python3 scripts/generate_template_generalization_report.py
python3 -m pytest
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

For routine validation while editing:

```bash
python3 -m pytest
python3 scripts/run_dev_eval.py
```

For final validation:

```bash
python3 scripts/warm_cache.py
python3 scripts/inspect_schema.py
python3 scripts/run_dev_eval.py
python3 scripts/generate_failure_analysis.py
python3 scripts/generate_family_score_report.py
python3 scripts/generate_pareto_report.py
python3 scripts/generate_template_generalization_report.py
python3 scripts/tune_thresholds.py
python3 scripts/run_robustness_eval.py
python3 -m pytest
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

## End-to-End System Data Flow Flowchart

`outputs/visualizations/end_to_end_system_dataflow.html` is an auto-generated, fully self-contained single vertical flowchart for the current DASHSys runtime and reporting workflow. It intentionally follows a Graphviz-style process diagram: top-to-bottom main runtime path, clustered sections, and dashed diagnostic side branches. It is not a dashboard: the HTML is one large SVG diagram covering prompt routing, query analysis, `SQL_FIRST_API_VERIFY`, SQL/API validation, live Adobe API versus dry-run fallback, EvidenceBus, answer synthesis, diagnostic-only paths, final packaging, and evaluation.

Refresh it with:

```bash
python3 scripts/generate_end_to_end_system_dataflow.py
```

The normal visualization and consolidated-report generators refresh it automatically. Do not manually edit the generated HTML/MD/JSON; update `scripts/generate_end_to_end_system_dataflow.py` and regenerate when workflow code changes.

Mandatory post-change validation after every code, report, cleanup, visualization, or documentation change:

```bash
python3 -m pytest -q
python3 scripts/generate_end_to_end_system_dataflow.py
python3 scripts/audit_workshop_requirements.py
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_hidden_style_eval.py
python3 scripts/check_llm_sdk_backend.py
python3 scripts/run_workflow_decision_audit.py
python3 scripts/run_decision_feedback_loop.py
python3 scripts/run_llm_baseline_eval.py
python3 scripts/run_llm_strict_baseline_eval.py
python3 scripts/run_llm_hidden_style_diagnostic.py
python3 scripts/generate_winner_readiness_report.py
python3 scripts/generate_research_inspired_report.py
python3 scripts/generate_system_status_dashboard.py
python3 scripts/generate_technique_visual_cards.py
python3 scripts/generate_visualization_index.py
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

After validation, regenerate the consolidated report surfaces:

```bash
python3 scripts/generate_consolidated_reports.py
python3 scripts/audit_workshop_requirements.py
python3 scripts/audit_redundant_files.py
python3 scripts/cleanup_redundant_files.py --dry-run --write-report
```

The workshop audit writes `outputs/reports/workshop_requirement_audit.md/json` and verifies official DASHSys tools, per-query deliverables, trajectory reproducibility, diagnostic-suite separation, SDK-only LLM usage, and final-submission packaging safety. If any command is skipped, record the command, reason, substitute validation, and residual risk in `outputs/reports/cleanup_final_report.md/json`. Run the secret scan before handoff and report the result:

```bash
OPENAI_KEY_PATTERN='OPENAI_API_KEY=.*s''k'
ANTHROPIC_KEY_PATTERN='ANTHROPIC_API_KEY=.*s''k'
AUTH_HEADER_PATTERN='Authorization:''\\s*''Bearer'
SECRET_SCAN_PATTERN="sk-[A-Za-z0-9_-]{12,}|${OPENAI_KEY_PATTERN}|${ANTHROPIC_KEY_PATTERN}|${AUTH_HEADER_PATTERN}"
rg -n "$SECRET_SCAN_PATTERN" . --glob '!.git/**' --glob '!.env.local' --glob '!*.zip' || true
```

Update `README.md`, this file, report indices, and visualization indices when script names, canonical report paths, setup commands, validation commands, LLM provider behavior, or cleanup-linked paths change. Final responses must include files changed, reports generated, files deleted, validation commands/results, skipped commands and reasons, `check_submission_ready` status, secret scan status, and confirmations that packaged `SQL_FIRST_API_VERIFY` behavior and final submission format are unchanged.

## Evaluation Expectations

Every correctness or efficiency improvement must be backed by `scripts/run_dev_eval.py`.

Track at least:

- SQL correctness
- API correctness
- answer correctness
- final score
- tool calls
- estimated tokens
- prompt tokens
- runtime
- preprocessing/context-selection time
- validation failures

Success criteria for optimization passes:

- Correctness improves or stays stable.
- Answer correctness improves or stays stable.
- Tool calls do not increase.
- Tokens and prompt size do not increase.
- Runtime stays stable or improves.
- Tests pass.
- Packaging and readiness pass.

## Coding Guidelines

- Use Python 3.11+.
- Keep changes small and localized.
- Prefer existing patterns and helper APIs.
- Use structured parsing/helpers instead of ad hoc string manipulation when possible.
- Add tests for new behavior.
- Keep metadata and trajectory previews compact.
- Preserve original user query text in outputs; use normalized text only for matching/planning.
- Keep `LLM_FREE_AGENT_BASELINE` as a baseline, not the production path.
- Do not delete or weaken validators to improve scores.
- Do not make API calls mandatory for every query.
- Do not introduce network calls except through the existing Adobe API client path.

## SQL And API Safety

SQL must remain read-only. Destructive or environment-changing SQL is blocked:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `CREATE`
- `COPY`
- `ATTACH`
- `DETACH`

API calls must match the endpoint catalog unless explicit fallback mode is enabled. Do not emit unresolved path placeholders such as `{schema_id}`. Unresolved parameter placeholders such as `<destination_id>` require explicit warnings and should be avoided when SQL evidence can forward the ID.

## Reporting And Packaging

Important generated reports:

- `outputs/eval_results.json`
- `outputs/strategy_comparison.md`
- `outputs/failure_analysis.md`
- `outputs/family_score_report.md`
- `outputs/pareto_report.md`
- `outputs/template_generalization_check.md`
- `outputs/threshold_tuning_report.md`
- `outputs/robustness_eval.md`

Final packaging should produce:

- `outputs/source_code.zip`
- `outputs/final_submission/`
- `outputs/final_submission_manifest.json`

Run `python3 scripts/check_submission_ready.py` before handing off final work.

## Known Current Direction

`SQL_FIRST_API_VERIFY` is the best default because it grounds entity names/IDs in local SQL before using API evidence only when needed. `TEMPLATE_FIRST` can be competitive on public examples but carries more overfitting risk and usually higher tool-call cost.

Highest-value remaining improvements are usually:

- richer answer templates for batch, tags, merge-policy, segment-job, observability, and recent-dataset families
- schema/dataset API path refinement
- hidden-query robustness without increasing prompt size or tool calls
