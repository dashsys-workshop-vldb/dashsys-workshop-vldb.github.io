# Concise LLM Rewrite Experiment

## Result

- Strategy implemented: `SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE`
- Packaged default unchanged: `SQL_FIRST_API_VERIFY`
- Tool path unchanged: `True`
- Focused tests: `52 passed`

## Organizer35

| strategy | final | answer | SQL | API | tool calls |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.658 | 0.3207 | 0.9333 | 0.9791 | 1.4571 |
| SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE | 0.6585 | 0.3207 | 0.9333 | 0.9791 | 1.4571 |

Deltas: `{'answer_delta': 0.0, 'api_delta': 0.0, 'final_delta': 0.0005, 'runtime_delta': -0.1331, 'sql_delta': 0.0, 'token_delta': 0.0857, 'tool_call_delta': 0.0}`
Rewrite counts: `{'not_attempted': 35, 'not_eligible': 35, 'rejected_or_skipped': 35}`
Selected source counts: `{'LEGACY_SAFE_RENDERER': 35}`
Unsupported claims: `0`

## Smoke

Selected source counts: `{'LEGACY_SAFE_RENDERER': 4}`
Rewrite category counts: `{'backend_unavailable': 1, 'not_attempted': 3}`

## Readiness

- `python3 scripts/check_submission_ready.py`: passed
- `git diff --check`: passed
- `python3 scripts/run_hidden_style_eval.py`: ran, 48 cases

## Remaining Blockers

- Organizer35 selected no concise rewrites; answer score stayed neutral.
- Smoke rewrite attempt hit LLM backend auth/401 and safely fell back to legacy.
- Most organizer rows were not eligible under conservative runtime-evidence/caveat rules.

No promotion recommendation.
