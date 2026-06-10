# Combined Safe Promotion Organizer 35 Dry Run

- Evaluator: `scripts/run_dev_eval.py --strict`
- Dataset: `data/data.json`
- Packaged default changed: `false`
- LLM advisor included: `false`

| Strategy | Final | Correctness | SQL | API | Answer | Tool calls | SQL calls | API calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6579 | 0.6850 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 0.4286 | 1.0286 | 0.6516 | 799.7143 |
| `COMBINED_SAFE_APPLIED_TRIAL` | 0.6583 | 0.6850 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 0.4286 | 1.0286 | 0.5356 | 799.6000 |
| `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE` | 0.6585 | 0.6850 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 0.4286 | 1.0286 | 0.4892 | 799.7143 |

## `COMBINED_SAFE_APPLIED_TRIAL` vs `SQL_FIRST_API_VERIFY`
- Helped/hurt/neutral: `6/1/28`
- API calls saved/added: `0/0`
- API_REQUIRED underuse: `0`
- Severe regression rows: `0`

## `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE` vs `SQL_FIRST_API_VERIFY`
- Helped/hurt/neutral: `7/1/27`
- API calls saved/added: `0/0`
- API_REQUIRED underuse: `0`
- Severe regression rows: `0`

## Gate
- Recommendation: `organizer35_candidate_passed`
- Blockers: `[]`
