# Combined Safe Promotion Patch Plan

- Apply now: `false`
- Candidate: `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`
- Default change proposed for future explicit approval: Change the packaged strategy/default submission strategy from SQL_FIRST_API_VERIFY to COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE only after explicit user approval.
- Excluded: Post-SQL LLM advisor, broad semantic router, semantic no-tool runtime promotion.

## Files To Review For Future Enablement
- `dashagent/agent_tools.py`
- `dashagent/executor.py`
- `scripts/package_query_outputs.py`
- `scripts/package_submission.py`
- `scripts/check_submission_ready.py`

## Validation After Enablement
- `python3 scripts/run_dev_eval.py --strict`
- `python3 scripts/run_hidden_style_eval.py`
- `python3 scripts/check_submission_ready.py`
- `python3 scripts/audit_workshop_requirements.py`
- `python3 scripts/generate_sdk_usage_audit.py`
- `python3 -m pytest -q`
- `git diff --check`
- `targeted secret scan`

## Rollback
- Revert packaged default strategy references to SQL_FIRST_API_VERIFY.
- Rerun package_submission.py and package_query_outputs.py.
- Rerun check_submission_ready.py and run_dev_eval.py --strict.
