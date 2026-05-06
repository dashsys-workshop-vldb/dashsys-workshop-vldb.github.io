# Score 0.75 Integration Diff Report

- Status: workers reported; no branches merged by integration.
- Baseline strict score/correctness: `0.6491 / 0.6743`
- Current integrated strict score/correctness: `0.6491 / 0.6743`
- 0.75 reached: `false`
- Merged branches: none

## Branch Decisions

| Branch | Decision | Reason | Strict Delta | Hidden Delta | Token Delta | Runtime Delta | Tool Delta | Final Submission Diff | No-Secret |
|---|---|---|---:|---|---:|---:|---:|---|---|
| `codex/score075-coordinator-baseline` | `pending` | Pairwise integration validation not run yet. | 0.0 | 0 | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-dryrun-answer` | `pending` | Pairwise integration validation not run yet. | None | None | None | None | None | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-local-index` | `pending` | Pairwise integration validation not run yet. | 0.0 | None | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-endpoint-routing` | `pending` | Pairwise integration validation not run yet. | None | None | None | None | None | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-candidate-generation` | `pending` | Pairwise integration validation not run yet. | None | None | None | None | None | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-execution-selector` | `blocked` | Work is not on its own branch or dependencies are missing. | 0.0 | 0 | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-llm-search` | `rejected_for_now` | No safe score-improving candidate available yet. | 0.0 | None | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-answer-shape` | `pending` | Pairwise integration validation not run yet. | None | None | None | None | None | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-robustness-leakage` | `pending_first_merge` | Should be validated first in merge order. | 0.0 | 0 | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |
| `codex/score075-integration` | `pending` | Pairwise integration validation not run yet. | 0.0 | 0 | 0.0 | 0.0 | 0.0 | not checked; worker did not intentionally touch final_submission | not checked by central integration |

## Notes

- No packaged trial has accepted any score-improving branch yet.
- The execution-selector work must be replayed onto its own branch before merge review.
- Final submission was not edited by this coordination update.
