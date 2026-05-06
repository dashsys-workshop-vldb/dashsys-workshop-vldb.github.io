# DASHSys Final Report And Visualization Polish Report

## 1. Summary

This pass polished only supervisor-facing reports and visualization clarity. `SQL_FIRST_API_VERIFY` remains the packaged default, strict evaluation was not changed, and all visualization artifacts stay under `outputs/visualizations/`.

Mermaid graphs now use short human-readable node labels instead of escaped JSON previews. Detailed values remain in Markdown tables and `dataflow_summary.json`.

## 2. Report Fixes

| Area | Before | After |
| --- | --- | --- |
| RAW/GUIDED summary cells | blank score/tool/token cells | populated with diagnostic `n/a - tool-loop diagnostic baseline`, average tool calls, prompt/context tokens, runtime, and LLM status |
| Successful tool-loop rows | duplicate query IDs without variant labels | `Variant` column labels Raw, Guided, or Optimized Controller |
| Dry-run wording | API dry-run could be confused with live evidence | report separates tool invocation/execution from live evidence availability |
| Provider failures | request-level failures were visible but not summarized | Provider Reliability Note added with Raw/GUIDED `llm_request_failed` counts |

Provider reliability counts from `outputs/baseline_comparison_report.json`:

| Variant | `llm_request_failed` count |
| --- | ---: |
| Raw | 8 |
| Guided | 9 |

Failed provider rows remain under failed real LLM tool loops and are not counted as successful tool-loop runs. They do not affect the packaged `SQL_FIRST_API_VERIFY` submission.

## 3. Evidence Labeling

Visualizations and comparison tables now split evidence labels:

| Label | Meaning |
| --- | --- |
| `sql_evidence_available` | Local SQL produced evidence usable for answering |
| `live_api_evidence_available` | Adobe API returned live evidence, not only dry-run metadata |
| `overall_evidence_available` | At least one evidence source was available |
| `dry_run_only` | API tool was invoked/validated, but live evidence was unavailable because credentials were missing |
| `successful_evidence_count` | Count of evidence-bearing tool results |

Example verification from `example_000` SQL_FIRST and Guided summaries: SQL evidence is `true`, live API evidence is `false`, overall evidence is `true`, and dry-run API is `true`.

## 4. Context Labels

When a trajectory records an explicit `context_mode`, the visualization uses it. When context artifacts exist but no explicit planner mode was recorded, the display now uses labels such as `candidate_like_context_inferred` or `metadata_context_card`.

These inferred labels are display-only; they are not treated as real planner decisions.

## 5. Visual Readability Gate

Gate check: count Mermaid lines containing `{&quot;`, `truncated_items`, or `preview`.

| Scope | Before | After |
| --- | ---: | ---: |
| Required SQL_FIRST Mermaid files (`example_000`, `example_004`, `example_031`, `list_all_journeys`) | 16 | 0 |
| Required SQL_FIRST + Raw/Guided baseline Mermaid files | n/a | 0 |

Full JSON/details now appear only in Markdown tables and `dataflow_summary.json`, not Mermaid nodes.

## 6. Generated Visualizations

Generated SQL_FIRST visualizations:

| Query ID | Dataflow Markdown | Dataflow HTML | Strategy comparison |
| --- | --- | --- | --- |
| `example_000` | [dataflow.md](visualizations/example_000/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_000/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_000/strategy_comparison.md) |
| `example_004` | [dataflow.md](visualizations/example_004/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_004/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_004/strategy_comparison.md) |
| `example_031` | [dataflow.md](visualizations/example_031/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_031/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_031/strategy_comparison.md) |
| `list_all_journeys` | [dataflow.md](visualizations/list_all_journeys/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/list_all_journeys/sql_first_api_verify/dataflow.html) | n/a |

Generated baseline coverage:

| Query ID | Raw baseline | Guided baseline |
| --- | --- | --- |
| `example_000` | [Raw dataflow.md](visualizations/example_000/raw_real_llm_two_tools_baseline/dataflow.md) | [Guided dataflow.md](visualizations/example_000/guided_real_llm_two_tools_baseline/dataflow.md) |
| `example_004` | [Raw dataflow.md](visualizations/example_004/raw_real_llm_two_tools_baseline/dataflow.md) | [Guided dataflow.md](visualizations/example_004/guided_real_llm_two_tools_baseline/dataflow.md) |
| `example_031` | [Raw dataflow.md](visualizations/example_031/raw_real_llm_two_tools_baseline/dataflow.md) | [Guided dataflow.md](visualizations/example_031/guided_real_llm_two_tools_baseline/dataflow.md) |

Global index:

- [outputs/visualizations/index.md](visualizations/index.md)
- [outputs/visualizations/index.html](visualizations/index.html)

The index includes SQL_FIRST, Raw, and Guided links with strategy, variant, tool calls, valid-run status, split evidence status, and badges.

## 7. Artifact Scope

Visualization outputs are written only under `outputs/visualizations/`. `outputs/final_submission/` contains no visualization files, and `package_query_outputs.py` still packages only required submission files.

## 8. SQL_FIRST Regression Result

Strict `SQL_FIRST_API_VERIFY` metrics after rerun:

| Metric | Value |
| --- | ---: |
| strict correctness | 0.6743 |
| strict final score | 0.6486 |
| estimated tokens | 899.2286 |
| average runtime | 0.0115 |

The packaged preferred strategy remains `SQL_FIRST_API_VERIFY`.

## 9. Validation Results

| Check | Result |
| --- | --- |
| `python3 -m pytest` | 154 passed |
| `python3 scripts/generate_baseline_comparison_report.py` | passed |
| `python3 scripts/generate_dataflow_visualization.py outputs/eval/example_000/sql_first_api_verify/trajectory.json` | passed |
| `python3 scripts/generate_all_dataflow_visualizations.py` | passed |
| `python3 scripts/generate_strategy_comparison_visualization.py --query-id example_000` | passed |
| `python3 scripts/generate_strategy_comparison_visualization.py --query-id example_004` | passed |
| `python3 scripts/generate_strategy_comparison_visualization.py --query-id example_031` | passed |
| `python3 scripts/run_dev_eval.py --strict` | passed |
| `python3 scripts/package_submission.py` | passed |
| `python3 scripts/package_query_outputs.py` | passed |
| `python3 scripts/check_submission_ready.py` | passed |
| `no_secret_scan.ok` | true |

## 10. Remaining Risks

- Adobe credentials are still unavailable, so API behavior remains dry-run and is not live evidence.
- Real LLM baseline rows remain provider/model-dependent; request-level failures are separated and reported.
- Candidate/context mode labels are clearer, but inferred labels are display-only and should not be read as planner choices.
- Guided baseline visualizations are useful for diagnosis, but `SQL_FIRST_API_VERIFY` remains the stable packaged strategy.

## 11. Targeted Stabilization Addendum

- Value retrieval cache filenames now use reproducible SHA-256 cache keys instead of Python process-salted `hash()` values.
- Value retrieval cache status is visible in dataflow reports when the retrieval checkpoint is active: `cache_hit`, `cache_key_algorithm`, `cache_reproducible`, `retrieval_ms`, and budget status.
- SQLGlot AST validation reporting now exposes parse errors, selected tables/columns, unknown tables/columns, destructive-command detection, and closest suggestions without changing `SQL_FIRST_API_VERIFY` execution behavior.
- Candidate context reports now include diagnostic-only `candidate_risk_clusters`; these clusters do not change candidate ranking, SQL/API generation, or answer behavior.
- Latest strict gate result remains stable: `SQL_FIRST_API_VERIFY` final score `0.6486`, correctness `0.6743`, tool calls `1.4571`, estimated-token overhead `5.57%`, runtime overhead `14.71%`.

## 12. Ranking-First Candidate Retrieval Addendum

- Added ranking/report-only hybrid candidate scoring and endpoint-family reranking. These diagnostics reduce candidate risk clusters but do not change executed `SQL_FIRST_API_VERIFY` SQL/API plans.
- Added reciprocal-rank-fusion diagnostics alongside weighted score fusion so ranking separation can be audited without relying only on calibrated weights.
- Added structural schema-preservation diagnostics and value-to-API ranking metrics; value boosts require high-confidence value matches and remain auditable.
- Added gated risk-cluster repair diagnostics with execution repair disabled by default.
- Candidate risk cluster gate passed:
  - `zero_score_margin`: 32 → 6
  - `missing_gold_api_in_top_k`: 15 → 7
  - `batch_endpoint_confusion`: 8 → 5
  - `tag_api_confusion`: 4 → 1
  - `schema_vs_dataset_confusion`: 4 → 0
- No score claim is made from these ranking-only changes: strict final score remains `0.6486`, strict correctness remains `0.6743`, and the report labels this as retrieval/candidate diagnostics improvement.
- `python3 -m pytest`: 145 passed. Strict eval, packaging, query output packaging, readiness, and `no_secret_scan.ok` all passed after this pass.

## 13. Offline Shadow Repair Evaluation Addendum

- Added `outputs/shadow_repair_eval.json`, `outputs/shadow_repair_eval.md`, and isolated per-query shadow decisions under `outputs/shadow_repair_eval/`.
- Shadow repair remains offline only: packaged `SQL_FIRST_API_VERIFY` execution, final submission format, and query output packaging are unchanged.
- Repeated shadow eval is deterministic: 35/35 `decision_hash` values matched across consecutive runs.
- Paired shadow summary:
  - repaired better: 1
  - repaired equal: 26
  - repaired worse: 8
  - unsafe repairs: 21
  - average score delta: -0.0357
  - average tool delta: 0.0286
  - average runtime delta: 0.0
- Cluster canary recommendations remain disabled by default. The shadow report recommends keeping repair execution disabled for target clusters because at least one safety, score, or efficiency gate fails.
- Dataflow visualizations now include a compact `Shadow Repair / What-if Evaluation` table when a shadow row is available, showing current candidate, repaired candidate, safety verdict, score/cost deltas, and enablement decision.
- Latest validation after the shadow pass:
  - `python3 -m pytest`: 154 passed
  - strict `SQL_FIRST_API_VERIFY` final score: 0.6486
  - strict correctness: 0.6743
  - average tool calls: 1.4571
  - preferred strategy: `SQL_FIRST_API_VERIFY`
  - `no_secret_scan.ok`: true

## 14. Risk-Based Efficiency And Schema Voting Addendum

- Extended the canonical `scripts/run_shadow_repair_eval.py` and `dashagent/repair_safety_verifier.py`; no duplicate shadow-repair or verifier modules were added.
- Added a diagnostic risk-based efficiency controller. It labels rows as low/medium/high risk and reports intended module policy, skipped modules, `token_saved_estimate`, and `runtime_saved_estimate_ms`.
- These savings are estimates only. No measured efficiency improvement is claimed because packaged `SQL_FIRST_API_VERIFY` execution did not skip modules or change selected plans.
- Added high-risk schema context voting. It compares compact candidate context against broader hybrid/full context and reports `schema_vote_agreement`, `compact_context_safe`, and fallback reason without changing executed SQL/API.
- Shadow repair output now includes risk policy and schema-vote fields per row, plus summary distributions. Current shadow summary reports deterministic decisions and repair execution remains disabled.
- Candidate report and dataflow visualization now include `Risk-Based Efficiency Controller` and `Schema Context Voting` sections.
- Packaged artifacts remain unchanged: shadow outputs stay under `outputs/shadow_repair_eval*`, visualizations stay under `outputs/visualizations/`, and no shadow/visualization files are written into `outputs/final_submission/`.
- Latest validation after the risk-efficiency/schema-vote pass:
  - `python3 -m pytest`: 162 passed
  - strict `SQL_FIRST_API_VERIFY` final score: 0.6486
  - strict correctness: 0.6743
  - average tool calls: 1.4571
  - estimated tokens: 899.2286
  - average runtime: 0.0115
  - preferred strategy: `SQL_FIRST_API_VERIFY`
  - repair execution enabled: false
  - `no_secret_scan.ok`: true
