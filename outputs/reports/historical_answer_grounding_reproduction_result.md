# Historical Answer Grounding Reproduction Result

- Worktree: `/tmp/dashsys-answer-repro`
- Commit: `fabcb0bcd1f2e1660e1e401f3ca9c86c50a95bbd`
- Command succeeded: `True`
- Reproduced 0.8884: `False`

| Strategy | Final | Correctness | SQL | API | Answer | SQL calls | API calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6566 | 0.6812 | 0.9333 | 0.9791 | 0.3223 | 15 | 36 |
| `ROBUST_ABLATION_ANSWER_GROUNDING_ONLY` | 0.6178 | 0.6451 | 0.9333 | 0.9791 | 0.2182 | 15 | 36 |
| `ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER` | 0.6179 | 0.6451 | 0.9333 | 0.9791 | 0.2182 | 15 | 36 |

Reason not reproduced: Old commit ran successfully, but current backend/environment produced EMPTY_LLM_ANSWER followed by fallback for 35/35 ablation rows; answer_score was 0.2182 and final_score about 0.6179, not 0.8884. Local historical trajectories tied to the report show empty final answers selected without fallback, indicating the high report is an artifact of the historical evaluator/trajectory state rather than a reproducible improvement.

## Current Main Sanity Checks

- check_submission_ready: `ok=true`
- git diff --check: `pass`
- focused tests: `14 passed`
- packaged default unchanged: `SQL_FIRST_API_VERIFY`
- credential values printed: `false`
- temporary reproduction worktree: `removed`
