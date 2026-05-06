# score075 Integration Diff Report

- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Current branch: `codex/score075-integration`
- Merged branches: 0
- Rejected branches: 0
- Pending branches: 10
- Strict score before/after/delta: 0.6491 / 0.6491 / 0.0
- Hidden-style before/after: 48/48 / 48/48
- Token/runtime/tool deltas: 0.0 / 0.0 / 0.0
- Final submission format unchanged: True
- No-secret result: True
- Recommendation: `no_merge_performed_pending_worker_dependencies`

## Branch Decisions

| Branch | Status | Dependencies | Merge recommendation | Score delta | Hidden delta |
|---|---:|---|---|---:|---:|
| `codex/score075-coordinator-baseline` | reported_complete_not_merged | - | pending_integration_validation | 0.0 | 0.0 |
| `codex/score075-dryrun-answer` | reported_complete_not_merged | codex/score075-local-index | pending_dependency_validation | 0.0 | 0.0 |
| `codex/score075-local-index` | reported_complete_not_merged | codex/score075-robustness-leakage | pending_dependency_validation | 0.0 | 0.0 |
| `codex/score075-endpoint-routing` | reported_complete_not_merged | codex/score075-robustness-leakage | pending_dependency_validation | 0.0 | 0.0 |
| `codex/score075-candidate-generation` | reported_complete_not_merged | codex/score075-local-index, codex/score075-answer-shape, codex/score075-endpoint-routing | pending_dependency_validation | 0.0 | 0.0 |
| `codex/score075-execution-selector` | reported_complete_not_merged | codex/score075-candidate-generation, codex/score075-robustness-leakage | keep_shadow_only_until_dependencies_merged | 0.0 | 0.0 |
| `codex/score075-llm-search` | not_reported_to_integration | codex/score075-robustness-leakage | blocked_missing_worker_result | 0.0 | 0.0 |
| `codex/score075-answer-shape` | not_reported_to_integration | codex/score075-robustness-leakage | blocked_missing_worker_result | 0.0 | 0.0 |
| `codex/score075-robustness-leakage` | not_reported_to_integration | - | blocked_missing_worker_result | 0.0 | 0.0 |
| `codex/score075-integration` | in_progress | all accepted worker branches | not_applicable_current_branch | 0.0 | 0.0 |
