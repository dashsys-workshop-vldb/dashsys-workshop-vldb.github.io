# Combined Safe Targeted Promotion Review

- Candidate strategy: `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`
- Packaged default changed: `false`
- Final submission format changed: `false`
- LLM advisor included: `false`
- Broad semantic router promoted: `false`

## Cross-Benchmark Summary
| Benchmark | Baseline | Candidate | Delta | API saved/added | API_REQUIRED underuse | Helped/Hurt/Neutral |
|---|---:|---:|---:|---:|---:|---:|
| Organizer 35 strict | 0.6579 | 0.6585 | 0.0006 | 0/0 | 0 | 7/1/27 |
| Internal 500 heuristic behavior | 0.8045 | 0.8089 | 0.0044 | 21/0 | 0 | 21/0/479 |
| Internal 500 organizer-style strict | 0.1620 | 0.1645 | 0.0025 | 21/0 | 0 | 48/4/448 |

## Validation
- Hidden-style: `48/48`
- check_submission_ready: `ok`
- Workshop audit: `pass`
- SDK runtime direct HTTP hits: `0`
- Pytest: `687 passed, 1 skipped`
- git diff --check: `passed`

## Recommendation
- `promote_combined_safe_deterministic_candidate`
- Blockers: `[]`
- Default was not flipped in this pass.
