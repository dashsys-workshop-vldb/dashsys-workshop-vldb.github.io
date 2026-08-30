# Score075 Robustness / Leakage Report

- Branch: `codex/score075-robustness-leakage`
- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Declared dependencies: none
- Packaged execution changed: false
- Writes final submission: false
- Scorer logic changed: false
- Hidden-style tests weakened: false

## Guards Added

- Reject query-id, exact-query, gold SQL/API, and memorized-answer triggers.
- Require general value-match provenance for exact public-entity triggers.
- Assert generated score075 candidates expose non-gold, generalizable trigger metadata.
- Enforce local-index evidence-object-only behavior when the local-index module is present.
- Assert dry-run answers ignore untrusted `result_preview` payload values and report live API evidence as unavailable.
- Assert selector gates reject leakage, evidence-label loss, fabricated live evidence, missing required fields, hidden-style regression, and candidate-diversity reduction.
- Assert hidden-style remains 48/48 with repair and compact context disabled.
- Assert diagnostic candidate search leaves `outputs/final_submission/` untouched.

## Validation

- `python3 -m pytest tests/test_score075_robustness_leakage.py tests/test_score_push_pipeline.py -q` -> 15 passed, 1 skipped.
- `python3 -m pytest -q` -> 240 passed, 1 skipped.

## Metrics

- Hidden-style result: 48/48.
- Family/schema stability: 1.0 / 1.0.
- Strict score delta: 0.0.
- Token/runtime/tool deltas: 0.0 / 0.0 / 0.0.

## Blockers

- The local-index evidence-object-only test uses `pytest.skip` until `codex/score075-local-index` is merged. After that branch is merged, the same test enforces that local-index hits are evidence objects, not final answers.
