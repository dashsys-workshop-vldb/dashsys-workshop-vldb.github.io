# score075 Execution Selector Handoff

- Branch: `codex/score075-execution-selector`
- Baseline: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Worker: execution-based selector
- Declared dependencies: `codex/score075-candidate-generation`, `codex/score075-robustness-leakage`
- Dependency status: blocked for promotion until integration merges or validates those branches first

## Allowed Files Used

- `dashagent/execution_based_candidate_selector.py`
- `scripts/run_execution_candidate_search.py`
- `tests/test_execution_based_candidate_selector.py`
- `outputs/execution_candidate_search.json`
- `outputs/execution_candidate_search.md`
- `outputs/execution_candidate_search/`
- `outputs/score075_execution_selector_handoff.md`

## Gate Strengthening

This branch adds explicit selector rejection checks for:

- invalid SQL validation or SQL AST validation
- unknown SQL tables and columns
- destructive SQL detection
- invalid or uncataloged API calls
- unresolved API path placeholders
- dry-run evidence label loss
- fabricated live API evidence
- token/runtime/tool cost regressions
- query-id and exact-query trigger features
- gold/memorized source signals
- hidden-style or candidate-diversity regressions

## Promotion Note

This worker produces candidates, selector gates, isolated evals, and reports only. It does not enable packaged behavior and does not write to final submission artifacts.
