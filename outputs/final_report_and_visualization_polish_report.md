# DASHSys Final Report And Visualization Polish Report

## 1. Summary Of Report Fixes

This pass polished the supervisor-facing reports and added detailed prompt-to-answer visualization artifacts. `SQL_FIRST_API_VERIFY` remains the packaged default, strict eval remains unchanged, and visualization files are kept under `outputs/visualizations/` only.

## 2. Baseline Report Before/After

| Area | Before | After |
| --- | --- | --- |
| RAW/GUIDED summary cells | blank score/tool/token cells in the summary table | populated with diagnostic `n/a - tool-loop diagnostic baseline`, average tool calls, prompt/context tokens, runtime, and LLM status |
| Successful tool-loop rows | repeated query IDs without variant labels | `Variant` column labels Raw, Guided, or Optimized Controller |
| Evidence wording | dry-run API could be confused with live evidence | report explains tool invocation/execution attempt vs evidence availability |
| Failed real LLM runs | separated from valid rows but less visible | failed rows remain separate and are not scored as successful baselines |

Confirmation: no blank RAW/GUIDED summary cells remain in `outputs/baseline_comparison_report.md`.

## 3. Raw/Guided Variant Labels

The successful real LLM tool-loop table now includes:

`Variant | Query ID | Tool calls | Tool calls executed? | Valid run? | Evidence count | Dry-run only? | Invalid calls | Endpoint repairs`

Duplicate query IDs are now disambiguated by Raw and Guided labels.

## 4. Dry-Run API Wording

Reports now consistently separate:

- `tool_invoked`
- `tool_execution_attempted`
- `tool_execution_ok`
- `evidence_available`
- `dry_run_only`

Dry-run API wording states: "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing." Dry-run API is not described as successful live evidence.

## 5. Visualization Files Generated

Detailed dataflow visualizations were generated for the required examples:

| Query ID | Dataflow Markdown | Dataflow HTML | Strategy comparison |
| --- | --- | --- | --- |
| `example_000` | [dataflow.md](visualizations/example_000/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_000/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_000/strategy_comparison.md) |
| `example_004` | [dataflow.md](visualizations/example_004/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_004/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_004/strategy_comparison.md) |
| `example_031` | [dataflow.md](visualizations/example_031/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/example_031/sql_first_api_verify/dataflow.html) | [strategy_comparison.md](visualizations/example_031/strategy_comparison.md) |
| `list_all_journeys` | [dataflow.md](visualizations/list_all_journeys/sql_first_api_verify/dataflow.md) | [dataflow.html](visualizations/list_all_journeys/sql_first_api_verify/dataflow.html) | n/a |

Global index:

- [outputs/visualizations/index.md](visualizations/index.md)
- [outputs/visualizations/index.html](visualizations/index.html)

## 6. Visualization Quality Gate

Each required `dataflow.md` shows:

- actual user query
- actual strategy name
- actual final answer preview
- actual `tool_call_count`
- SQL/API preview or `n/a` with reason
- dry-run and evidence status
- checkpoint count
- at least one checkpoint-derived correctness or efficiency effect

The Mermaid graph includes subgraphs for Input, Routing, Query Understanding, Context Selection, Planning, SQL Path, API Path, Tool Execution, EvidenceBus, Answer Verification, Final Answer, and Metrics.

## 7. Artifact Scope

Visualization outputs are written only under `outputs/visualizations/`. `outputs/final_submission/` contains no visualization files, and `package_query_outputs.py` still packages only required submission files.

## 8. SQL_FIRST Regression Result

Strict `SQL_FIRST_API_VERIFY` metrics after rerun:

| Metric | Value |
| --- | ---: |
| strict correctness | 0.6743 |
| strict final score | 0.649 |
| estimated tokens | 851.7714 |
| average runtime | 0.0105 |

The packaged preferred strategy remains `SQL_FIRST_API_VERIFY`.

## 9. Validation Results

| Check | Result |
| --- | --- |
| `python3 -m pytest` | 108 passed |
| `python3 scripts/run_llm_baseline_eval.py` | passed with provider-backed rows; failed provider-request rows are separated |
| `python3 scripts/generate_candidate_context_report.py` | passed |
| `python3 scripts/generate_baseline_comparison_report.py` | passed |
| `python3 scripts/run_dev_eval.py --strict` | passed |
| `python3 scripts/package_submission.py` | passed |
| `python3 scripts/package_query_outputs.py` | passed |
| `python3 scripts/check_submission_ready.py` | passed |
| `no_secret_scan.ok` | true |

## 10. Remaining Risks

- Adobe credentials are still unavailable, so local API behavior remains dry-run.
- Real LLM baseline runs remain provider/model-dependent; the latest provider-backed run had request-level failures in later examples.
- Candidate context still often recommends hybrid fallback because many examples have low confidence or zero score margin.
- Guided baseline improves invalid-call behavior but costs more prompt/context tokens than raw.
