# Overnight Iteration 1 Plan

- Goal: Trial and, only if gated validation passes, promote a generic answer-only dry-run endpoint wording improvement.
- Expected improvement: Improve answer score on dry-run API rows where the selected endpoint/params are real evidence but live payload is unavailable; no SQL/API/tool changes expected.
- Risk level: `medium-low`
- Packaged behavior may change: `True`
- Files to edit: `dashagent/config.py`, `dashagent/answer_templates.py`, `tests/test_answer_correctness_layer.py`
- Safety controls: feature flag first, answer-only only, SQL/API calls unchanged, tool count unchanged, no live API evidence fabrication, full strict eval before promotion
- Rollback condition: Revert behavior-changing edits if strict score does not improve, correctness regresses, hidden-style/readiness/secret scan fails, or SQL/API/tool hashes drift for answer-only rows.
- Cleanup policy: dry-run only; no file deletion in overnight loop
