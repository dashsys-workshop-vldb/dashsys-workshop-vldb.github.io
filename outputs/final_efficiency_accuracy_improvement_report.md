# DASHSys Efficiency And Accuracy Improvement Report

## Executive Summary

DASHSys remains stable on the packaged path: `SQL_FIRST_API_VERIFY` is still the default submission strategy, strict scoring still passes, and no secret leakage was detected in the submission checks. The raw and guided real-LLM tool-loop baselines are now clearly separated. In the latest OpenRouter-backed run, guided mode sharply reduced invalid tool behavior, especially unknown-table and unsupported-negative-answer failures, while using more prompt/context tokens. Several late real-provider requests failed at the LLM-request level; those rows are reported as failed tool loops and are not counted as successful baselines.

## What Changed

- Split real LLM tool diagnostics into `RAW_REAL_LLM_TWO_TOOLS_BASELINE` and `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE`.
- Added guided-only schema affordance, endpoint repair, virtual schema guidance, validation feedback, duplicate-call tracking, and uncertainty-safe answer wording.
- Added evidence availability fields so reports separate tool invocation from usable evidence.
- Added adaptive candidate context modes: `candidate`, `expanded_candidate`, `hybrid`, and `full_schema`.
- Added detailed dataflow visualization reports under `outputs/visualizations/`.

## What Did Not Change

- `SQL_FIRST_API_VERIFY` remains the packaged default.
- Strict evaluation was not weakened; missing gold fields remain unscored rather than free `1.0`.
- Validators, secret redaction, checkpoint logging, packaging, and readiness checks remain in place.
- Adobe API remains dry-run when credentials are unavailable; dry-run API calls are not live evidence.
- Raw baseline remains the fair naive real LLM + two tools comparison.

## Raw vs Guided Comparison

| Metric | Raw baseline | Guided baseline |
| --- | ---: | ---: |
| Rows | 35 | 35 |
| Successful tool-loop rows | 27 | 26 |
| Failed tool-loop rows | 8 | 9 |
| Valid run rate | 0.7714 | 0.7429 |
| Average tool calls | 1.2571 | 1.2 |
| Average invalid tool calls | 0.3143 | 0.0286 |
| Unknown table errors | 9 | 0 |
| Unsupported negative answers | 4 | 0 |
| Endpoint repairs | 0 | 22 total / 0.6286 average |
| Average prompt/context tokens | 1318.3429 | 2057.3429 |
| Average runtime | 4.8366 | 3.625 |

Guided mode costs more context because it gives the model allowed tables, API affordances, and actionable feedback. The fresh provider run had several request-level failures for both variants; those are model/provider reliability issues rather than successful or scored tool-loop runs. Among completed tool loops, guided mode still reduced invalid calls and removed unknown-table failures.

## Tool Execution vs Evidence Success

Dry-run API calls mean the tool was invoked and validated, and execution was attempted through the DASHSys API wrapper, but live evidence was unavailable because Adobe credentials were missing. These calls are not counted as successful live evidence.

| Metric | Raw | Guided |
| --- | ---: | ---: |
| Dry-run-only API count | 15 | 24 |
| Average successful evidence count | 0.3714 | 0.2857 |
| Average invalid tool calls | 0.3143 | 0.0286 |

## Empty-Result Uncertainty

When SQL returns zero rows through an inferred schema or after prior validation issues, the baseline wording avoids hard negatives such as "not found" or "does not exist." It uses uncertainty phrasing such as: "The executed query did not find evidence for X." This keeps failed or weak tool paths from becoming unsupported factual claims.

## Endpoint Repair Examples

Guided endpoint repair is catalog-constrained. For batch-file style requests, aliases like `/data/core/ups/batch/{id}/files` are repaired to `/data/foundation/export/batches/{batch_id}/files` when the endpoint family and extracted ID are safe. The report records original endpoint, repaired endpoint, reason, and confidence.

## Schema Feedback Examples

Guided validation feedback explains invalid generic table choices. For example, a journey/campaign prompt that tries `journey` is pointed toward allowed schema such as `dim_campaign`; introspection attempts like `information_schema` and `sqlite_master` return guided schema feedback instead of being treated as real database internals.

## Candidate Context Mode Distribution

| Metric | Value |
| --- | ---: |
| Candidate context tokens | 896.4857 |
| Full schema context tokens | 4682 |
| Compression ratio | 0.1915 |
| Table recall@3 | 0.7444 |
| Table recall@5 | 0.8222 |
| API recall@3 | 0.4677 |
| API recall@5 | 0.5484 |
| Low-confidence count | 14 |
| Zero-margin count | 32 |
| Recommended fallback rate | 0.9143 |

| Context mode | Count |
| --- | ---: |
| candidate | 3 |
| hybrid | 32 |

Candidate context is useful for compression, but the low-confidence and zero-margin rate remains high enough that hybrid/full-schema fallback is still required for robustness.

## Curated Join Hint Audit

`outputs/candidate_context_report.json` includes `curated_join_hint_audit`. The audit reports `used_gold_patterns: false`; join hints are classified as schema-level relationships, naming conventions, bridge-table heuristics, or manual general rules. No join hint is derived from gold SQL, exact public query strings, or public answer patterns.

## Before/After Regression Table

| Gate | Result |
| --- | --- |
| `SQL_FIRST_API_VERIFY` strict final score | 0.649, no material regression |
| `SQL_FIRST_API_VERIFY` strict correctness | 0.6743 |
| `SQL_FIRST_API_VERIFY` estimated tokens | 851.7714 |
| `SQL_FIRST_API_VERIFY` runtime | 0.0105 |
| Packaged preferred strategy | `SQL_FIRST_API_VERIFY` |
| Strict missing-gold behavior | preserved |
| Raw baseline availability | available |
| Guided baseline reporting | separate from raw |

## Failure-Category Table

| Category | Raw | Guided | Result |
| --- | ---: | ---: | --- |
| unknown_table_count | 9 | 0 | improved |
| unknown_column_count | 1 | 1 | stable |
| unknown_endpoint_count | 0 | 0 | stable |
| schema_introspection_failure_count | 4 | 1 | improved |
| duplicate_invalid_call_count | 0 | 0 | stable |
| dry_run_only_api_count | 15 | 24 | guided reaches more API paths, still dry-run-only without Adobe credentials |
| unsupported_negative_answer_count | 4 | 0 | improved |
| max_turns_exceeded_count | 0 | 0 | stable |
| no_final_answer_count | 8 | 9 | provider request failures in this run; failed rows stay separate |

## Token And Runtime Efficiency

| Metric | Raw | Guided | Interpretation |
| --- | ---: | ---: | --- |
| Avg prompt/context tokens | 1318.3429 | 2057.3429 | Guided costs more context |
| Avg runtime | 4.8366 | 3.625 | Guided was faster in this provider run despite larger context |
| Avg invalid tool calls | 0.3143 | 0.0286 | Guided reduces wasted invalid calls |
| Valid run rate | 0.7714 | 0.7429 | Provider request failures affected guided late rows |

## Strict Eval, Packaging, Readiness

- `python3 -m pytest`: 108 passed.
- `python3 scripts/run_dev_eval.py --strict`: passed.
- Packaging and readiness are rerun in the final validation step.
- Visualization files are generated only under `outputs/visualizations/` and are not part of `outputs/final_submission/`.

## Remaining Issues

- Adobe credentials are unavailable locally, so API evidence remains dry-run.
- Candidate context still has many low-confidence or zero-margin cases.
- Guided baseline costs more tokens than raw.
- Real LLM baseline behavior is provider/model-dependent and can fail at request time.

## Next Steps

- Re-run with Adobe credentials to measure live API evidence.
- Re-run provider-backed baselines after rate/request stability improves.
- Tune candidate retrieval only with hidden-test-safe schema/API retrieval rules.
- Keep `SQL_FIRST_API_VERIFY` as default unless an LLM path beats it under strict scoring and efficiency checks.
