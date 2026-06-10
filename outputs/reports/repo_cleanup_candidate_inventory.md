# Repo Cleanup Candidate Inventory

- Generated at: `2026-05-19T14:12:12Z`
- Runtime behavior changed: `False`

## Classification Rules

- Protected artifacts, linked final reports, validation scripts, packaged runtime code, and final submission artifacts are kept.
- Unpromoted diagnostic/trial output directories are delete candidates only when final md/json reports exist.
- Large or heavily referenced candidates are left for manual review.
- The first deletion batch must stay under 50 files and 50 MB.

## Recommended Actions

- `keep`: `197` paths
- `manual_review`: `14` paths

## Delete Candidates


## Manual Review

- `dashagent/__pycache__`
- `node_modules`
- `outputs/autonomous_packaged_trial`
- `outputs/diagnostic_prompt_suite`
- `outputs/evidence_aware_answer_rewrite_trial`
- `outputs/generated_prompt_suite_diagnostic`
- `outputs/generated_prompt_suite_local_diagnostic`
- `outputs/live_api_evidence_pipeline_trial`
- `outputs/llm_semantic_router_isolated_trial`
- `outputs/mock_live_api_evidence_pipeline_trial`
- `outputs/official_token_reduction_packaged_trial`
- `outputs/score_focused_core_improvement_trials`
- `scripts/__pycache__`
- `tests/__pycache__`
