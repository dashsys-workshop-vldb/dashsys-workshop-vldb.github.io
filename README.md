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

Adobe credentials are optional for local/public evaluation. Missing credentials put API calls in dry-run mode. Live Adobe API readiness is the target for future connected runs; dry-run is only the honest local fallback.

```bash
export CLIENT_ID=...
export CLIENT_SECRET=...
export IMS_ORG=...
export SANDBOX=...
export ACCESS_TOKEN=...
export ADOBE_BASE_URL=https://platform.adobe.io
```

Preferred Adobe aliases are also supported: `ADOBE_ACCESS_TOKEN`, `ADOBE_API_KEY`, `ADOBE_ORG_ID`, `ADOBE_SANDBOX_NAME`, `ADOBE_CLIENT_ID`, and `ADOBE_CLIENT_SECRET`. Reports may show only source labels and booleans such as `primary`, `alias`, `default`, `missing`, `true`, or `false`; they must not show tokens, API keys, client IDs, client secrets, org IDs, sandbox names, or masked prefixes.

### Local Adobe Credentials

Use committed placeholders plus a local untracked env file:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` locally with real values only:

```bash
ADOBE_ACCESS_TOKEN = ...
ADOBE_API_KEY = ...
ADOBE_ORG_ID = ...
ADOBE_SANDBOX_NAME = ...
ADOBE_BASE_URL = https://platform.adobe.io
```

Check status without exposing secrets:

```bash
python3 scripts/check_adobe_env_local.py
```

Then run live readiness checks:

```bash
python3 scripts/audit_live_adobe_api_readiness.py
python3 scripts/run_live_api_readiness_smoke.py
python3 scripts/run_live_api_evidence_pipeline_trial.py
```

Never commit `.env.local`.

While Adobe org/sandbox permissions are pending, run the offline diagnostic with:

```bash
python3 scripts/run_generated_prompt_suite_local_diagnostic.py
```

After permissions are granted, run:

```bash
python3 scripts/run_post_permission_live_api_verification.py
```

This post-permission runner performs only the minimal safe live verification sequence and does not run full live strict eval or the full live generated prompt suite.

Real LLM integration is also optional. OpenAI remains the default provider:

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
```

OpenRouter and self-hosted vLLM endpoints are supported through the OpenAI SDK-compatible client path:

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="..."
export OPENROUTER_MODEL="openai/gpt-4o-mini"
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

OpenRouter support is optional. Not all OpenRouter models support native tool/function calling; for the real two-tool baselines, use a model with reliable tool calling.

No credentials are required for tests. Secrets are redacted from trajectories and reports.

## 3.1 System-Wide SDK-Based LLM Rule

All LLM/model calls must go through `dashagent.llm_client.get_llm_client()` or the shared `LLMClient` abstraction. OpenAI-compatible providers use `from openai import OpenAI`; Anthropic providers use `from anthropic import Anthropic`. Do not add raw `requests`, `curl`, direct `/chat/completions`, or hand-built provider HTTP calls for LLM runtime testing, baselines, diagnostics, report generation, or future model-assisted scripts.

The LLM baseline framework is the generic SDK-based LLM baseline framework. Qwen, GPT, Claude, Llama, OpenRouter models, or local vLLM models are backend metadata selected through `.env.local` and environment variables, not separate framework names. Run the SDK audit with:

```bash
python3 scripts/generate_sdk_usage_audit.py
```

The audit report is written to `outputs/reports/sdk_usage_audit.md/json` and must show `runtime_llm_direct_http_hits = 0`.

## 3.2 LLM Semantic Routing Helper

`dashagent/semantic_routing_helper.py` is an optional SDK-based routing-hint helper for low-confidence or ambiguous prompts. It is default-off with `ENABLE_LLM_SEMANTIC_ROUTER=false` and shadow-only by default with `LLM_SEMANTIC_ROUTER_SHADOW_ONLY=true`.

The helper may suggest validated domain, route, intent, synonym, table, and API-family hints only. It must never produce final answers, SQL/API results, or tool calls, and it must never bypass SQL/API validators. Non-shadow use is isolated-trial only and must not affect packaged submission unless a later explicit strict/safety promotion approves it.

Run the shadow diagnostic with:

```bash
python3 scripts/run_llm_semantic_router_shadow_eval.py --limit 50
```

The report is written to `outputs/reports/llm_semantic_router_shadow_eval.md/json`.

## 3.3 Diagnostic Prompt Suite

The generated diagnostic prompt suite broadens coverage testing from `data/data.json` without changing official scoring or packaged behavior.

```bash
python3 scripts/generate_diagnostic_prompt_suite.py
python3 scripts/run_diagnostic_prompt_suite.py
python3 scripts/run_diagnostic_prompt_suite.py --full
python3 scripts/run_diagnostic_prompt_suite.py --limit 50
python3 scripts/run_diagnostic_prompt_suite.py --clean
python3 scripts/run_diagnostic_prompt_suite.py --with-llm-semantic-router-shadow
```

Outputs:

- `data/generated_prompt_suite.json`
- `data/generated_prompt_suite.md`
- `outputs/reports/generated_prompt_suite_summary.md/json`
- `outputs/reports/diagnostic_prompt_suite_run.md/json`

Generated prompts are diagnostic-only, `should_be_scored=false`, not used as official benchmark data, and excluded from final submission packaging.

`scripts/run_generated_prompt_suite_local_diagnostic.py` runs the full suite in dry-run-safe local mode, even when live Adobe credentials exist. Its vague-answer and missing-count/name heuristics are advisory only and cannot support official score claims or promotion.

Use `python3 scripts/analyze_generated_prompt_local_diagnostic_gaps.py` after the local diagnostic to inspect representative mismatch samples and write `outputs/reports/local_deterministic_improvement_candidates.md`. It proposes only evidence-gated future fixes and does not change runtime behavior.

For a Superpowers-style improvement pass, run:

```bash
python3 scripts/run_superpowers_next_steps_preflight.py
python3 scripts/review_local_diagnostic_gap_candidates.py
```

These reports protect `outputs/final_submission/**`, strict/hidden eval artifacts, endpoint catalog paths, and packaged defaults. Generated labels are compared against actual route/domain/evidence behavior before any mismatch is treated as a true bug. If no single low-risk deterministic candidate passes the evidence gate, no runtime change is applied.

## 3.4 Context7 Documentation-Grounded Audit

Use Context7 for external documentation lookup only. Do not print or commit Context7 API keys, Adobe credentials, or raw Authorization/header values. Before changing behavior tied to an external SDK, library, or API, run:

```bash
python3 scripts/run_context7_code_alignment_audit.py
```

The audit writes `outputs/reports/context7_docs_audit_preflight.md/json`, `outputs/reports/context7_dependency_docs_summary.md/json`, `outputs/reports/context7_code_alignment_audit.md/json`, and `outputs/reports/context7_fix_decision.md/json`. Reports store short findings and library IDs, not raw docs. No runtime change should be applied unless `context7_fix_decision` documents a small docs-proven issue, focused tests, and no-regression validation. Live Adobe API data success still requires at least one safe GET endpoint returning `live_success`.

## 3.5 Decision-Stage Feedback Loops

Serious improvement candidates must start from a workflow decision-stage question, not a module guess. Use:

```bash
python3 scripts/run_workflow_decision_audit.py
python3 scripts/run_decision_feedback_loop.py
```

The required process is hypothesis → baseline → isolated trial → failure analysis → 3-5 controlled variants → evidence-backed decision. Do not reject a serious candidate after one failed run; report whether a variant failed, the candidate is partially useful, the candidate is not viable after feedback loops, or the candidate is eligible for future limited promotion.

Generated diagnostic prompts are coverage-only and cannot support official strict-score improvement or promotion claims. Answer-only trials must preserve SQL hash, API hash, tool count, selected evidence hash, and dry-run label. Behavior-changing variants stay in isolated outputs unless a later human-reviewed strict/safety promotion explicitly approves them.

## 3.6 Live Adobe API Readiness

Live Adobe API readiness is infrastructure validation, not score promotion. The system keeps `API_REQUIRED` calls required in live mode, uses catalog-approved Adobe REST calls, and falls back to dry-run only when credentials are unavailable. No live API evidence may be fabricated, and live smoke/trial reports must not overwrite `outputs/eval/`, `outputs/eval_results_strict.json`, `outputs/final_submission/`, or `outputs/final_submission_manifest.json`.

Run:

```bash
python3 scripts/audit_live_adobe_api_readiness.py
python3 scripts/generate_api_required_readiness_matrix.py
python3 scripts/run_live_api_readiness_smoke.py
python3 scripts/run_live_api_evidence_pipeline_trial.py
python3 scripts/run_mock_live_api_evidence_pipeline_trial.py
```

Reports are written under `outputs/reports/` and isolated live trial artifacts under `outputs/live_api_evidence_pipeline_trial/` or `outputs/mock_live_api_evidence_pipeline_trial/`. Safe smoke tests are GET-only by default and do not call endpoints with unresolved path parameters unless a discovery step supplies a safe ID. The API response parser normalizes live payloads into `parsed_evidence`, EvidenceBus forwards parsed IDs/names/statuses/counts/timestamps/errors/pagination, and answer slots track whether evidence came from live API, dry-run fallback, empty live results, or API errors.

Discovery chains are GET-only, never guess IDs, and record provenance for discovered IDs. Mocked fixtures under `tests/fixtures/adobe_api_responses/` validate endpoint-family parsing before credentials arrive; they are synthetic and must not be used as official benchmark evidence.

Client-credentials token acquisition is supported through the same local `.env.local` setup. Current live smoke diagnostics can show token readiness while endpoint-level calls still fail because of product permission, sandbox scope, endpoint path, or Adobe service behavior. Run `python3 scripts/run_live_api_endpoint_path_diagnosis.py` and inspect `outputs/reports/live_api_external_blockers.md` before any full live prompt suite. Large live runs are guarded by structured smoke JSON and stay blocked until at least one catalog-approved safe GET endpoint returns `live_success`, unless an explicit diagnostic-only CLI override is used. Generated prompts remain diagnostic-only, and no live API data success should be claimed before a safe GET `live_success`.

Use `outputs/reports/live_api_endpoint_followup_commands.md` for safe rerun commands such as `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id <endpoint_id>`, `--endpoint-family <family>`, and `--limit all-safe-get`. These commands never include credentials.

Use `outputs/reports/adobe_access_waiting_status.md` for the short supervisor-facing access status. After external access changes, `python3 scripts/run_post_permission_live_api_verification.py` reruns the minimal safe sequence and reports whether guarded full live runs are allowed.

## 3.6 Evidence-Aware Answer Synthesis

Evidence-aware answer synthesis is an isolated answer-only feedback loop. It audits whether final answers use SQL/API evidence, proposes deterministic template rewrites, and verifies faithfulness without rerunning SQL or API calls.

```bash
python3 scripts/run_evidence_usage_audit.py
python3 scripts/run_evidence_aware_answer_rewrite_trial.py
python3 scripts/run_sql_evidence_usage_audit.py
python3 scripts/run_confidence_calibration_audit.py
python3 scripts/run_token_efficiency_audit.py
```

The rewrite trial writes only under `outputs/evidence_aware_answer_rewrite_trial/`. Any answer-only promotion requires invariant SQL hash, API hash, tool count, selected evidence hash, route, plan, and dry-run labels; unsupported claims must not increase; hidden-style must remain 48/48; and `check_submission_ready.py` must pass. Dry-run caveats remain required for `API_REQUIRED` rows when live API verification is unavailable.

## 3.7 Score-Focused Direct Path Trials

Use the full project dataflow SVG as a map for score-producing code, not as an optimization target. The direct score path is prompt understanding, deterministic routing/domain/intent, `SQL_FIRST_API_VERIFY`, SQL/API planning and validation, EvidenceBus, answer slots, answer synthesis, verifier output, and final trajectory packaging.

```bash
python3 scripts/run_score_path_contribution_audit.py
python3 scripts/run_score_focused_core_improvement_trials.py
```

These scripts write `outputs/reports/score_path_contribution_audit.md/json`, `outputs/reports/score_focused_core_improvement_trials.md/json`, and `outputs/reports/score_focused_core_fix_decision.md/json`. They are isolated diagnostics: they must not overwrite `outputs/eval_results_strict.json`, `outputs/eval/`, `outputs/final_submission/`, or final submission manifests. A runtime change may be promoted only if a general deterministic variant improves strict score, preserves hidden-style 48/48, passes `check_submission_ready.py`, does not increase unsupported claims, and leaves final-submission format unchanged. The current trial decision is `keep_trial_only`; no runtime code path was promoted.

## 3.8 Comprehensive Failure Analysis

Use the comprehensive failure analysis when deciding whether an implementation prompt is justified. It combines official public/dev strict rows for real score-loss diagnosis with generated prompt diagnostics for generality and coverage only.

```bash
python3 scripts/run_comprehensive_failure_analysis.py
```

The script writes official row failure tables, generated prompt failure tables, cross-dataset clusters, candidate general deterministic rules, counterfactual answer sketches, a hardcoding-risk audit, and `outputs/reports/comprehensive_failure_fix_decision.md/json`. It is analysis-only: generated prompts are never official score evidence, counterfactual sketches are report-only, and no runtime change, endpoint catalog change, packaged-strategy change, or final-submission change is allowed in this pass. Any future rule must use general signals such as intent, route/domain, SQL result shape, EvidenceBus fields, API state, and answer-slot type; never query IDs, prompt IDs, exact prompt strings, or gold answers.

## 3.9 Type-Specific Deterministic Rule Discovery

Use type-specific rule discovery when looking for several small non-LLM fast paths instead of one broad rewrite. It groups official rows and generated diagnostics by prompt type, domain, execution need, and evidence shape, then runs isolated simulations for rule families such as SQL-only fast paths, count/list/status/date answer fast paths, zero-row local-evidence wording, API caveat ordering, router synonym candidates, and unknown/ambiguous fallbacks.

```bash
python3 scripts/run_deterministic_prompt_type_audit.py
python3 scripts/run_type_specific_deterministic_rule_trials.py
```

The outputs are `outputs/reports/deterministic_prompt_type_audit.md/json`, `outputs/reports/type_specific_deterministic_rule_candidates.md/json`, `outputs/reports/type_specific_deterministic_rule_trials.md/json`, and `outputs/reports/type_specific_rule_fix_decision.md/json`. These reports are diagnostic and isolated: generated prompts are used only for generality/speed evidence, official rows remain the score evidence, and no runtime rule is promoted unless a later implementation pass proves strict/hidden-style/submission safety. Current type-specific trials identify speed-only candidates but keep `runtime_change_applied=false`.

## 3.10 SDK Tool Calling Optimization Audit

Use the SDK tool-calling optimization audit for shadow-only analysis of LLM tool policy, schema compactness, tool-result verbosity, and rewrite gates. It does not replace `SQL_FIRST_API_VERIFY`, does not run live Adobe API calls, and must not overwrite strict eval or final-submission artifacts.

```bash
python3 scripts/run_sdk_tool_calling_optimization_audit.py
python3 scripts/run_sdk_tool_calling_optimization_trials.py
python3 scripts/run_sdk_tool_calling_efficiency_promotion.py --validation-complete
python3 scripts/run_tool_calling_policy_optimizer.py
```

The audit reports are `outputs/reports/sdk_tool_calling_optimization_preflight.md/json`, `outputs/reports/sdk_tool_call_surface_audit.md/json`, `outputs/reports/sdk_tool_call_decision_analysis.md/json`, `outputs/reports/sdk_tool_call_optimization_variants.md/json`, `outputs/reports/sdk_tool_calling_optimization_trials.md/json`, and `outputs/reports/sdk_tool_calling_fix_decision.md/json`. The promotion reports are `outputs/reports/sdk_tool_calling_promotion_preflight.md/json`, `outputs/reports/sdk_tool_calling_promotion_plan.md/json`, and `outputs/reports/sdk_tool_calling_efficiency_promotion_decision.md/json`. A small speed-only SDK tool-call patch is promoted only after strict score stays unchanged, hidden-style remains 48/48, `check_submission_ready.py` passes, SDK direct HTTP hits remain `0`, and final-submission format stays unchanged. This does not replace `SQL_FIRST_API_VERIFY` or broadly promote the LLM controller/semantic router/answer rewrite paths.

## 3.11 Correctness + Efficiency Evaluation

Organizer evaluation includes both correctness and efficiency. Correctness-only strict score is not the whole picture: efficiency also includes agent turns, tool calls, total tokens, wall time, and end-to-end runtime including preprocessing/context selection where the artifacts expose it.

```bash
python3 scripts/run_correctness_efficiency_scorecard.py
```

The scorecard writes `outputs/reports/correctness_efficiency_scorecard.md/json` and `outputs/reports/correctness_efficiency_fix_decision.md/json`. Because official organizer weights are unknown, it reports sensitivity scenarios instead of fabricating an official overall score: correctness-dominant, balanced, efficiency-sensitive, strict-no-regression efficiency rank, and hidden-safe efficiency rank. Speed-only candidates with `strict delta = 0.0` can be valuable, but a runtime patch still requires no correctness regression, hidden-style 48/48, `check_submission_ready.py`, direct LLM HTTP hits `0`, no unsupported-claim increase, no hardcoding, and unchanged final-submission format.

## 3.12 Core Tool Optimization

Use the core tool optimizer for offline search and conservative deterministic policies inside the two official tools: `execute_sql(sql)` and `call_api(method, url, params, headers)`. This is not a broad LLM/controller promotion and does not replace `SQL_FIRST_API_VERIFY`.

```bash
python3 scripts/run_core_tool_optimization_audit.py
python3 scripts/run_core_tool_policy_optimizer.py
```

The reports are `outputs/reports/core_tool_optimization_audit.md/json`, `outputs/reports/core_tool_optimization_search_space.md/json`, `outputs/reports/core_tool_policy_optimizer.md/json`, `outputs/reports/core_tool_policy_search_results.md/json`, `outputs/reports/execute_sql_optimization_candidates.md/json`, `outputs/reports/call_api_optimization_candidates.md/json`, `outputs/reports/core_tool_compiled_policy_candidate.md/json`, and `outputs/reports/core_tool_policy_promotion_decision.md/json`.

The promoted low-risk policy keeps SQL read-only and Adobe data endpoints GET-only. It adds exact SQL validation caching, per-query duplicate API attempt reuse, and compact API outcome summaries while keeping optional API suppression report-only until strict/live validation proves no API score loss. No official organizer-weighted score is claimed because weights are unknown.

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

Start with the consolidated supervisor/submission report index:

```text
outputs/reports/report_index.md
```

It summarizes the useful generated evidence and points to the smaller set of canonical reports and visualizations.

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

## End-to-End System Data Flow Flowchart

`outputs/visualizations/end_to_end_system_dataflow.html` is an auto-generated, fully self-contained single vertical flowchart for the current DASHSys workflow. It intentionally follows a Graphviz-style process diagram: top-to-bottom main runtime path, clustered sections, and dashed diagnostic side branches. It is not a dashboard: the HTML is one large SVG diagram covering runtime, SQL path, Adobe API path, EvidenceBus, answer synthesis, diagnostics, packaging, and evaluation.

Refresh it with:

```bash
python3 scripts/generate_end_to_end_system_dataflow.py
```

Normal visualization and consolidated-report regeneration refreshes it too. Do not manually edit the generated HTML/MD/JSON; update `scripts/generate_end_to_end_system_dataflow.py` and regenerate when the workflow changes.

## Full Project Dataflow SVG

`outputs/visualizations/full_project_dataflow.svg` is the recommended single-diagram overview for supervisor walkthroughs. It is one large, locally generated SVG that covers the complete DASHSys dataflow: user prompts, query understanding, packaged `SQL_FIRST_API_VERIFY`, SQL/API guards, Adobe live-readiness guard, EvidenceBus, answer synthesis, diagnostics, evaluation, reporting, visualization, packaging, and final submission.

Refresh it with:

```bash
python3 scripts/generate_full_project_dataflow_svg.py
```

The generator reads current reports and project module/script names only. It must not access `.env.local`, credential files, external rendering services, or live Adobe endpoints, and it must not change runtime behavior or final-submission format.

## Project-Level Mermaid Visualization Workflow

`scripts/generate_project_mermaid_visualizations.py` creates text-based, versionable Mermaid diagrams from current reports and project module/script names only. It writes a C4-style architecture diagram, an end-to-end pipeline flow, a live Adobe API guard/status flow, a report dependency map, and `outputs/reports/visualization_sync_audit.md/json` with source-report SHA-256 hashes.

Refresh it with:

```bash
python3 scripts/generate_project_mermaid_visualizations.py
```

`generate_consolidated_reports.py` runs this workflow automatically. The diagrams must remain local, report-derived, and secret-safe: do not access `.env.local`, do not call external live services, and do not change runtime behavior to update a visualization.

## DASHSys Project Skill

Use this skill before any serious Codex change: [`skills/dashsys_project_skill/SKILL.md`](skills/dashsys_project_skill/SKILL.md).

The Skill protects final submission and official eval artifacts, separates correctness from efficiency work, keeps generated prompts diagnostic-only, blocks live eval until the live_success guard allows it, forbids hardcoding, and requires strict validation before promotion. It is repo-local and does not auto-install into a user home directory.

## 17. Mandatory Post-Change Validation

After every code, report, cleanup, visualization, or documentation change, run the full validation suite before calling the work complete:

```bash
python3 -m pytest -q
python3 scripts/audit_dashsys_project_skill.py
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
python3 scripts/generate_project_mermaid_visualizations.py
python3 scripts/generate_full_project_dataflow_svg.py
python3 scripts/run_score_path_contribution_audit.py
python3 scripts/run_score_focused_core_improvement_trials.py
python3 scripts/run_comprehensive_failure_analysis.py
python3 scripts/run_deterministic_prompt_type_audit.py
python3 scripts/run_type_specific_deterministic_rule_trials.py
python3 scripts/run_tool_calling_policy_optimizer.py
python3 scripts/run_core_tool_optimization_audit.py
python3 scripts/run_core_tool_policy_optimizer.py
python3 scripts/generate_visualization_index.py
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

Then regenerate the consolidated report entry point:

```bash
python3 scripts/generate_consolidated_reports.py
python3 scripts/audit_workshop_requirements.py
python3 scripts/audit_redundant_files.py
python3 scripts/cleanup_redundant_files.py --dry-run --write-report
```

The workshop audit writes `outputs/reports/workshop_requirement_audit.md/json` and checks official DASHSys deliverables, trajectory reproducibility, diagnostic-suite separation, SDK-only LLM usage, and final-submission packaging safety. If a command is impossible or too expensive in the current environment, record the skipped command, reason, substitute validation, and residual risk in `outputs/reports/cleanup_final_report.md/json`. Also run the secret scan:

```bash
OPENAI_KEY_PATTERN='OPENAI_API_KEY=.*s''k'
ANTHROPIC_KEY_PATTERN='ANTHROPIC_API_KEY=.*s''k'
AUTH_HEADER_PATTERN='Authorization:''\\s*''Bearer'
SECRET_SCAN_PATTERN="sk-[A-Za-z0-9_-]{12,}|${OPENAI_KEY_PATTERN}|${ANTHROPIC_KEY_PATTERN}|${AUTH_HEADER_PATTERN}"
rg -n "$SECRET_SCAN_PATTERN" . --glob '!.git/**' --glob '!.env.local' --glob '!*.zip' || true
```

Update this README, `AGENTS.md`, report indices, or visualization indices whenever script names, canonical report locations, setup commands, validation commands, LLM baseline behavior, or cleanup-linked paths change. Final handoff notes should include files changed, reports generated, deleted files, validation results, skipped commands, readiness status, secret scan status, and confirmations that `SQL_FIRST_API_VERIFY` and the final submission format are unchanged.

## 18. Safety Rules

- Keep `SQL_FIRST_API_VERIFY` as the deterministic default.
- Do not hard-code public-example answers, exact public query strings, or hidden-test assumptions.
- Keep SQL read-only; validators block destructive statements.
- API calls must match the endpoint catalog unless explicit fallback mode is enabled.
- Never commit credentials or generated secrets.
- Do not remove checkpoint logging, validation, secret redaction, packaging, or readiness checks.
