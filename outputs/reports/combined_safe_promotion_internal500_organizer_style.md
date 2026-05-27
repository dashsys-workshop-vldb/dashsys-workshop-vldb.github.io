# Combined Safe Promotion Internal 500 Organizer-Style Strict Dry Run

- Evaluator: `scripts/run_dev_eval.py --strict --dataset data/benchmarks/dashagent_500_organizer_style.json`
- Organizer-equivalent: `false`
- LLM advisor included: `false`
- Severe row definition: API underuse, validation/error regression, or final score delta <= -0.05.

| Strategy | Final | Correctness | SQL | API | Answer | Tool calls | SQL calls | API calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.1620 | 0.1874 | 0.0216 | 0.5282 | 0.1147 | 1.4400 | 0.7860 | 0.6540 | 0.3118 | 760.2840 |
| `COMBINED_SAFE_APPLIED_TRIAL` | 0.1645 | 0.1891 | 0.0216 | 0.5282 | 0.1186 | 1.3980 | 0.7860 | 0.6120 | 0.2491 | 751.2760 |
| `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE` | 0.1645 | 0.1891 | 0.0216 | 0.5282 | 0.1186 | 1.3980 | 0.7860 | 0.6120 | 0.2471 | 751.3180 |

## Candidate vs `SQL_FIRST_API_VERIFY`
- Helped/hurt/neutral: `48/4/448`
- API calls saved/added: `21/0`
- API_REQUIRED underuse: `0`
- Small non-severe hurt rows: `4`
- Severe regression rows: `0`

## Gate
- Recommendation: `internal500_organizer_style_candidate_passed`
- Blockers: `[]`
