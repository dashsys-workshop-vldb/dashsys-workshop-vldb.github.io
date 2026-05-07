# Score 0.75 Parallel Status

- Generated at: `2026-05-07T00:13:51.969645+00:00`
- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Final recommendation: `submit_current_official_token_reduction_version`

| Branch | Owner | Status | Latest Commit | Score Delta | Hidden | Recommendation | Blockers |
|---|---|---|---|---:|---|---|---|
| `codex/score075-coordinator-baseline` | coordinator/baseline | `rejected` | `b8d5892f` | 0.0 | 48/48 | `do_not_promote` | not merged after inspection |
| `codex/score075-robustness-leakage` | robustness/leakage | `merged` | `8447a040` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-local-index` | local Parquet knowledge index | `merged` | `38c5cbe0` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-dryrun-answer` | evidence-aware dry-run answers | `rejected` | `667e1515` | 0.0 | 48/48 | `do_not_promote` | strict_final_score remained 0.6491; no safe improvement |
| `codex/score075-answer-shape` | answer-shape optimization | `merged` | `4ba04c76` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-endpoint-routing` | endpoint/schema routing | `merged` | `9cae9dea` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-candidate-generation` | candidate generation | `merged` | `7228e0cb` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-execution-selector` | execution-based selector | `merged` | `0c161570` | 0.0 | 48/48 | `keep_on_integration_branch` | - |
| `codex/score075-llm-search` | LLM-assisted candidate search | `rejected` | `4c39f478` | 0.0 | 48/48 | `do_not_promote` | candidate_rows=0; safe_rows=0; recommendation=keep_shadow_only |
