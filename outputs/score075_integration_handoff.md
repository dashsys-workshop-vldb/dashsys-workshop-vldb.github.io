# score075 Integration Handoff

- Branch: `codex/score075-integration`
- Baseline SHA: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Scope: integration scaffolding, autonomous packaged-trial report, autonomous 0.75 score-push report, integration diff report, report integration, and query-output packaging exclusions.

## What This Branch Does

- Adds `scripts/run_autonomous_packaged_trial.py`.
- Adds `scripts/generate_autonomous_score_push_report.py`.
- Updates winner/readiness and research reports to summarize autonomous score-push and integration-diff artifacts when present.
- Excludes `outputs/autonomous_packaged_trial/` and `outputs/score075_*` directories from query-output packaging discovery.
- Adds the new autonomous scripts to source packaging.

## What This Branch Does Not Do

- Does not merge worker branches.
- Does not enable any score075 candidate behavior.
- Does not write to `outputs/eval/`.
- Does not write to `outputs/final_submission/`.
- Does not claim success below `strict_final_score >= 0.7500`.

## Current Integration Metrics

- Autonomous packaged trial recommendation: `submit_current_official_token_reduction_version`
- Autonomous 0.75 hard target reached: `false`
- Merged worker branches: `0`
- Rejected worker branches: `0`
- Pending worker branches: `10`
- Final submission readiness check: `ok=true`
- No-secret scan: `ok=true`

## Validation Run

- `python3 -m py_compile scripts/run_autonomous_packaged_trial.py scripts/generate_autonomous_score_push_report.py scripts/generate_winner_readiness_report.py scripts/generate_research_inspired_report.py scripts/package_query_outputs.py scripts/package_submission.py`
- `python3 scripts/run_autonomous_packaged_trial.py`
- `python3 scripts/generate_autonomous_score_push_report.py`
- `python3 scripts/generate_winner_readiness_report.py`
- `python3 scripts/generate_research_inspired_report.py`
- `python3 -m pytest`
- `python3 scripts/check_submission_ready.py`

## Blockers

- Worker branches have reported results but are not merged into this integration branch.
- `codex/score075-robustness-leakage`, `codex/score075-answer-shape`, and `codex/score075-llm-search` have no completed integration-ready notification in this thread.
- Pairwise merge validation must be run by integration before any branch can be accepted.
