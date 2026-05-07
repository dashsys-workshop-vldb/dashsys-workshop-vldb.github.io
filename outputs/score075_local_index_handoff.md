# Worker 3 Handoff: Local Parquet Knowledge Index

- Branch: `codex/score075-local-index`
- Baseline: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Dependency: `codex/score075-robustness-leakage`
- Status: candidate infrastructure ready; no packaged behavior enabled

## What This Branch Provides

- `dashagent/local_knowledge_index.py` builds a Parquet-only evidence-object index from `data/DBSnapshot/*.parquet`.
- `scripts/build_local_knowledge_index.py` writes `outputs/local_knowledge_index_report.json` and `.md`.
- `scripts/run_local_index_candidate_eval.py` writes `outputs/local_index_candidate_eval.json` and `.md`.
- `tests/test_local_knowledge_index.py` verifies provenance, no `data/data.json` runtime use, evidence-object-only behavior, and report-only candidate evaluation.

## Safety Boundaries

- The index returns evidence objects only, never final answers.
- Runtime generation must not read `data/data.json` gold traces, answers, SQL, or API paths.
- This branch does not edit final submission, official eval outputs, scorer logic, hidden-style tests, repair execution, or compact context.
- `safe_for_packaged_trial` remains `false` for all local-index rows; integration must run any future packaged trial.

## Integration Notes

- If integration wants these scripts included in source packaging, add them from the integration branch rather than this worker branch.
- Consume local-index hits only as recorded evidence for normal answer composition.
- Do not promote local-index behavior until robustness/leakage gates and full strict/hidden/package validation pass.
