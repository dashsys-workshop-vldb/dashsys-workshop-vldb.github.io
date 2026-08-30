# Combined Safe Default Final Gate

- Recommendation: `reverted_to_sql_first_api_verify`
- Candidate was enabled temporarily, but was not kept as packaged default.
- Candidate organizer-35 final before rollback: `0.6539`
- Required previous SQL_FIRST baseline: `0.6579`
- Fresh SQL_FIRST strict final after rollback: `0.6507`
- check_submission_ready ok: `True`
- hidden-style: `48/48`
- pytest: `692 passed, 1 skipped in 45.60s`
- git diff --check: `pass`
- secret scan real hits: `0`
- API_REQUIRED underuse: `0`
- Unsupported claims: `0`
- LLM advisor excluded: `true`
- Broad semantic router excluded: `true`
- Final submission format unchanged: `true`

Blockers:
- `candidate_final_score_below_previous_sql_first_baseline`
- `default_reverted_to_sql_first_api_verify_after_failed_gate`
