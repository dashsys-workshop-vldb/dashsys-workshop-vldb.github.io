# Post-Live Robustness Preflight

- Current branch: `codex/schema-aware-sql-fallback`
- Current strict score: `0.6554`
- Previous pre-live baseline: `0.6553`
- Initial live regression score: `0.6247`
- Endpoint matrix: `{'live_empty': 5, 'live_success': 10}`
- Active arbitration policy: `sql_primary_when_complete`
- check_submission_ready ok: `True`

## Known Risks

- template dependency remains the main NL-to-SQL generalization risk
- schema-aware fallback previously regressed strict score and remains keep_trial_only
- pure LLM tool-grounding is weaker than deterministic SQL_FIRST_API_VERIFY
- generated prompts need post-live diagnostic rerun
- multi-LLM robustness is diagnostic-only and not a packaged promotion gate yet
