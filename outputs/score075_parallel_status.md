# Score 0.75 Parallel Status

- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Baseline strict score/correctness: `0.6491 / 0.6743`
- Baseline tokens/runtime/tools: `831.4571 / 0.0115 / 1.4571`
- Hidden-style: `48/48`
- Global status: all workers reported; no integration merges performed

## Blockers

- Untracked duplicate outputs/final_submission/* 2.* artifacts exist in the baseline workspace; workers must not edit final_submission directly.
- Execution-selector changes must be replayed or moved to codex/score075-execution-selector before integration because they are currently dirty in the shared dryrun worktree.

## Workers

| Branch | Owner | Status | Dependencies | Latest Commit | Tests Run | Score Delta | Hidden-Style | Merge Recommendation | Blockers |
|---|---|---|---|---|---|---:|---|---|---|
| `codex/score075-coordinator-baseline` | coordinator/baseline | `completed_uncommitted_isolated_worktree` | none | `b583624c` | py_compile coordinator scripts<br>autonomous_improvement_loop --initialize-coordinator<br>generate_improvement_backlog to /tmp<br>generate_autonomous_score_push_report to /tmp | 0.0 | 48/48 | `pending_integration_review` | Source packaging inclusion is integration-owned<br>score075_integration_diff_report is integration-owned |
| `codex/score075-dryrun-answer` | evidence-aware dry-run answers | `completed_committed` | codex/score075-local-index | `667e1515` | pytest tests/test_answer_correctness_layer.py: 11 passed<br>pytest: 241 passed | n/a | not run by worker | `pending_after_local_index_contract` | Local-index evidence integration blocked pending local-index merge |
| `codex/score075-local-index` | local Parquet knowledge index | `completed_uncommitted_isolated_worktree` | codex/score075-robustness-leakage | `b583624c` | pytest tests/test_local_knowledge_index.py: 5 passed<br>pytest: 238 passed<br>build_local_knowledge_index<br>run_local_index_candidate_eval | 0.0 | not changed | `pending_after_robustness_merge` | Needs robustness/leakage branch merged first<br>Packaging inclusion is integration-owned |
| `codex/score075-endpoint-routing` | endpoint/schema routing | `completed_uncommitted_isolated_worktree` | codex/score075-robustness-leakage | `b583624c` | pytest endpoint/schema targeted tests: 6 passed | n/a | gate passed | `candidate_for_integration_after_robustness` | Needs robustness/leakage branch merged first |
| `codex/score075-candidate-generation` | candidate generation | `completed_uncommitted_isolated_worktree` | codex/score075-local-index, codex/score075-endpoint-routing, codex/score075-answer-shape | `b583624c` | pytest candidate generation + score push: 12 passed<br>run_score075_candidate_generation_eval | n/a | not changed | `ready_for_selector_after_dependencies` | Local-index API missing until dependency merge<br>Answer-shape API missing until dependency merge |
| `codex/score075-execution-selector` | execution-based selector | `completed_changes_misplaced_in_shared_dryrun_worktree` | codex/score075-candidate-generation, codex/score075-robustness-leakage | `b583624c` | pytest selector + score push: 13 passed<br>run_execution_candidate_search | 0.0 | 48/48 from existing report | `not_merge_ready_until_replayed_on_branch` | Changes are currently uncommitted in shared codex/score075-dryrun-answer worktree, not on codex/score075-execution-selector branch<br>Needs candidate-generation and robustness dependencies |
| `codex/score075-llm-search` | LLM-assisted candidate search | `completed_committed` | codex/score075-candidate-generation, codex/score075-execution-selector | `4c39f478` | pytest llm candidate/search/client targeted: 12 passed<br>run_llm_candidate_search without keys: skipped_no_llm_key<br>pytest: 237 passed | 0.0 | not changed | `keep_shadow_only_until_dependencies_and_keyed_eval` | No LLM key present<br>Depends on candidate generation and selector |
| `codex/score075-answer-shape` | answer-shape optimization | `completed_committed` | codex/score075-robustness-leakage | `4ba04c76` | pytest answer shape + answer correctness: 15 passed<br>pytest: 240 passed | n/a | not changed | `candidate_for_integration_after_robustness` | Needs robustness/leakage branch merged first |
| `codex/score075-robustness-leakage` | robustness/leakage tests | `completed_committed` | none | `8447a040` | pytest score075 robustness + score push: 15 passed, 1 skipped<br>pytest: 240 passed, 1 skipped | 0.0 | 48/48; family/schema 1.0/1.0 | `first_merge_candidate` | Local-index evidence-object-only test skipped until local-index merge |
| `codex/score075-integration` | integration/validation | `completed_committed_scaffolding_only` | all accepted worker branches | `f8852012` | py_compile integration scripts<br>run_autonomous_packaged_trial<br>generate_autonomous_score_push_report<br>generate_winner_readiness_report<br>generate_research_inspired_report<br>pytest: 233 passed<br>check_submission_ready: ok=true | 0.0 | 48/48 | `scaffolding_ready_no_branches_merged` | Pairwise merge validation still required<br>No worker branches merged yet |
