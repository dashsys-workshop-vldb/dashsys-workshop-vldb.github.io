# Worker 9 Handoff: Robustness / Leakage

- Branch: `codex/score075-robustness-leakage`
- Baseline: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Dependencies: none
- Merge recommendation: merge before candidate-producing branches so the guards protect integration.

## Changed Files

- `tests/test_score075_robustness_leakage.py`
- `outputs/score075_robustness_report.json`
- `outputs/score075_robustness_report.md`
- `outputs/score075_robustness_leakage_handoff.md`

## Coverage

- Query-id, exact-query, gold, and memorized-answer trigger rejection.
- General value-match requirement for exact public-entity trigger metadata.
- Non-gold/generalizable metadata on generated score075 candidates.
- Local-index evidence-object-only contract when `dashagent.local_knowledge_index` is present.
- Dry-run unavailable-field behavior: dry-run result previews are not treated as payload evidence.
- Selector and holdout gates for leakage, fabricated live evidence, evidence-label loss, hidden-style regression, and candidate-diversity loss.
- Hidden-style 48/48 with repair execution and compact context disabled.
- No final-submission writes from diagnostic search.

## Tests Run

- `python3 -m pytest tests/test_score075_robustness_leakage.py tests/test_score_push_pipeline.py -q` -> 15 passed, 1 skipped.
- `python3 -m pytest -q` -> 240 passed, 1 skipped.

## Notes For Integration

- One skip is expected on this baseline because `dashagent.local_knowledge_index` is not merged yet. Once `codex/score075-local-index` is merged, the test will run and enforce the evidence-object-only/no-gold/no-answer-cache contract.
- This worker did not edit runtime code, scorer code, hidden-style expectations, packaging, or final-submission artifacts.
