# Combined Safe Promotion Internal 500 Heuristic Dry Run

- Eval engine: `real_agent`
- Grading: `heuristic_internal_gold`
- Organizer-equivalent: `false`
- Runtime input fields: `prompt_id`, `prompt`
- LLM advisor included: `false`

| Mode | Behavior | Trace Observability | Combined Diagnostic | Final Answer | SQL Calls | API Calls | API Saved | Unsupported | No-tool FP | API_REQUIRED underuse | Helped | Hurt | Neutral | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `packaged_baseline_real` | 0.8045 | 0.2495 | 0.6995 | 0.6530 | 393 | 327 | 0 | 0 | 0 | 0 | 0 | 0 | 500 | 0.0000 | 0.0000 |
| `combined_safe_applied_real_trial` | 0.8089 | 0.4993 | 0.7265 | 0.6583 | 393 | 306 | 21 | 0 | 0 | 0 | 21 | 0 | 479 | 47.3194 | 998.7660 |
| `combined_safe_deterministic_promotion_candidate_real` | 0.8089 | 0.3743 | 0.7160 | 0.6583 | 393 | 306 | 21 | 0 | 0 | 0 | 21 | 0 | 479 | 41.8204 | 998.7660 |

## Gate
- Recommendation: `combined_safe_deterministic_candidate_for_targeted_promotion`
- Candidate passed: `True`
- Candidate blockers: `[]`
