# Score 0.75 Parallel Status

- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Best achieved strict score: 0.6558
- Strict score delta: 0.0067
- 0.75 reached: False
- Hidden-style result: 48/48
- Supportable answer safe rows/projected score: 4 / 0.6552
- Answer-shape v2 safe rows/projected score: 7 / 0.6497
- LLM answer rewrite status/model/accepted: completed / openrouter/free / 0/6
- Trial recommendation: `continue_iteration_target_not_reached`
- Final recommendation: `continue_iteration_target_not_reached`

| Branch | Owner | Status | Score delta | Hidden-style | Merge recommendation | Blockers |
|---|---|---|---:|---|---|---|
| `codex/score075-coordinator-baseline` | coordinator/baseline | reported_complete_not_merged | 0.0 | 48/48 | pending_integration_validation | not_merged_by_integration_worker |
| `codex/score075-dryrun-answer` | evidence-aware dry-run answers | reported_complete_not_merged | 0.0 | 48/48 | pending_dependency_validation | not_merged_by_integration_worker |
| `codex/score075-local-index` | local Parquet knowledge index | reported_complete_not_merged | 0.0 | 48/48 | pending_dependency_validation | not_merged_by_integration_worker |
| `codex/score075-endpoint-routing` | endpoint/schema routing | reported_complete_not_merged | 0.0 | 48/48 | pending_dependency_validation | not_merged_by_integration_worker |
| `codex/score075-candidate-generation` | candidate generation | reported_complete_not_merged | 0.0 | 48/48 | pending_dependency_validation | not_merged_by_integration_worker |
| `codex/score075-execution-selector` | execution-based selector | reported_complete_not_merged | 0.0 | 48/48 | keep_shadow_only_until_dependencies_merged | not_merged_by_integration_worker |
| `codex/score075-llm-search` | LLM-assisted candidate search | not_reported_to_integration | 0.0 | 48/48 | blocked_missing_worker_result | not_merged_by_integration_worker |
| `codex/score075-answer-shape` | answer-shape optimization | not_reported_to_integration | 0.0 | 48/48 | blocked_missing_worker_result | not_merged_by_integration_worker |
| `codex/score075-robustness-leakage` | robustness/leakage tests | not_reported_to_integration | 0.0 | 48/48 | blocked_missing_worker_result | not_merged_by_integration_worker |
| `codex/score075-integration` | integration/validation | in_progress | 0.0 | 48/48 | not_applicable_current_branch | not_merged_by_integration_worker |
| `main` | evidence-cited short answer rewrite | completed_isolated_progress_not_promoted | 0.0067 | 48/48 | keep_isolated_bundle_continue_iteration_target_not_reached | hard target strict_final_score >= 0.7500 not reached; LLM answer rewrite search status=completed safe_rows=0 |
