# Worker 7 LLM Search Handoff

- Branch: `codex/score075-llm-search`
- Dependencies: `codex/score075-candidate-generation`, `codex/score075-execution-selector`
- Allowed files: `dashagent/llm_candidate_generator.py`, `scripts/run_llm_candidate_search.py`, LLM-search tests, `outputs/llm_candidate_search.*`, `outputs/score075_llm_search_handoff.md`
- Status: `skipped_no_llm_key`
- Recommendation: `keep_shadow_only`
- Candidate rows: 0
- Safe for execution search: 0
- Packaged execution changed: false
- Final submission touched: false

## Notes

- No candidate is packaged by this worker.
- All keyed candidates must pass deterministic leakage, SQL, and API validators before handoff.
- Gold labels, gold SQL/API, gold answers, query IDs, and exact public query strings are not prompt inputs or trigger features.
