# Combined Safe Default Organizer 35 Final

- Previous SQL_FIRST baseline final: `0.6579`
- Gate passed: `False`
- Recommendation: `revert_to_sql_first_api_verify`
- Blockers: `['candidate_final_score_below_previous_sql_first_baseline']`

| Strategy | Final | Correctness | SQL | API | Answer | API calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6533 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 36 | 2.0581 | 799.2000 |
| `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE` | 0.6539 | 0.6851 | 0.9333 | 0.9791 | 0.3209 | 36 | 1.8819 | 799.2571 |

- Helped/hurt/neutral: `9/8/18`
- API_REQUIRED underuse: `0`
