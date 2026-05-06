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
| strict final score | 0.649 |
| estimated tokens | 851.7714 |
| average runtime | 0.0102 |

The packaged preferred strategy remains `SQL_FIRST_API_VERIFY`.

## 9. Validation Results

| Check | Result |
| --- | --- |
| `python3 -m pytest` | 109 passed |
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
