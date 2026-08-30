# Historical Answer Grounding Reject Decision

- Decision: `old_result_invalid_due_to_evaluator_artifact`
- Recommendation: `old_result_invalid_due_to_leakage`

Why:

- Tracked report with 0.8884 exists at fabcb0bcd1.
- Local historical trajectories for both answer-grounding modes contain 35/35 empty final answers selected from the LLM generator with fallback false.
- Historical score_answer_strict gave empty generated answers 0.85 because empty string is a substring of the gold answer.
- Old commit rerun did not reproduce 0.8884; it produced answer_score 0.2182 and final_score about 0.6179 for LLM_ANSWER_WITH_VERIFIER.

Clean alternative: Keep SQL/API path fixed, require non-empty verified LLM answer content, keep answer_candidate_selector fallback, and evaluate with empty-answer guard before considering any answer-layer port.

## Current Main Sanity Checks

- check_submission_ready: `ok=true`
- git diff --check: `pass`
- focused tests: `14 passed`
- packaged default unchanged: `SQL_FIRST_API_VERIFY`
- credential values printed: `false`
