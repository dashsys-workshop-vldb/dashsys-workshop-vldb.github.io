# Minimal Progressive Candidate Eval Summary

- Promotion gate: `not_run`
- Default flip: `not_run`
- Packaged default: `SQL_FIRST_API_VERIFY`
- Packaged default unchanged: `True`
- Final submission format unchanged: `True`

## Focused Tests
- `59 passed in 13.89s`

## Smoke Queries

| Query | Entry | Route | SQL | API | Unsupported | Notes |
|---|---|---|---:|---:|---:|---|
| `min_eval_concept_list_reasons` | `LLM_DIRECT` | `LLM_SAFE_DIRECT` | 0 | 0 | 0 | ok |
| `min_eval_meta_list_schemas` | `LLM_DIRECT` | `LLM_SAFE_DIRECT` | 0 | 0 | 0 | ok |
| `min_eval_current_schemas` | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | ok |
| `min_eval_inactive_journeys` | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | ok |
| `min_eval_local_schema_count` | `EVIDENCE_PIPELINE` | `SQL_ONLY` | 1 | 1 | 0 | local count still made API call; safe but inefficient |
| `min_eval_live_schema_count` | `EVIDENCE_PIPELINE` | `SQL_THEN_API` | 1 | 1 | 0 | ok |

## Organizer 35 Strict

| Strategy | Final | Answer | API |
|---|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6578 | 0.3207 | 0.9791 |
| `ROBUST_GENERALIZED_HARNESS_CANDIDATE` | 0.5339 | 0.1543 | 0.8553 |

- Helped/hurt/neutral: `{'helped': 2, 'hurt': 33, 'neutral': 0}`
- API_REQUIRED underuse-like rows: `0`
- No-tool false-positive-like rows: `0`
- Severe regression rows: `19`

## Internal 500 Balanced Subset

| Mode | Behavior | Final Answer | API Underuse | No-tool FP | Unsupported | SQL Calls | API Calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| `packaged_baseline_real` | 0.7708 | 0.605 | 0 | 0 | 0 | 30 | 39 |
| `robust_generalized_harness_candidate_real` | 0.805 | 0.63 | 0 | 4 | 0 | 24 | 27 |

- Helped/hurt/neutral: `{'helped': 10, 'hurt': 4, 'neutral': 36}`
- API call delta: `-12`
- Runtime delta ms: `822.5566`
- Token delta: `-252.94`

## Safety And Readiness
- SAFE_API_PROBE rows inspected: `12`; unsafe/unresolved blocks: `0`
- check_submission_ready ok: `True`
- hidden-style: `48/48`
- git diff --check return code: `0`

## Known Blockers / Next Targets
- Organizer 35 answer/final score regressed materially for the candidate; answer grounding/rendering is the main strict-eval blocker.
- Internal 50 subset still has 4 wrong no-tool skips in hard-stress mixed/evidence prompts.
- Local-snapshot schema count still preserved an API call; safe but inefficient.
- Smoke post-SQL LLM decision checkpoints were present but v1 decisions were null; risk-minimizing fallback handled API preservation. Unit tests cover correction feedback, but live smoke did not exercise a successful LLM revision.

Reports:
- `outputs/reports/minimal_progressive_candidate_eval_preflight.md`
- `outputs/reports/minimal_progressive_smoke_results.md`
- `outputs/reports/minimal_organizer35_progressive_check.md`
- `outputs/reports/minimal_internal500_progressive_subset.md`
