
# Research Generalized V2 Evaluation Summary

Implemented: yes
Generalized planner used instead of SQL_FIRST base: yes
Packaged default unchanged: `SQL_FIRST_API_VERIFY`

## Organizer 35

| Strategy | Final | SQL | API | Answer | Tool calls |
|---|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6562 | 0.9333 | 0.9791 | 0.3207 | 1.4571 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 | 0.6348 | 0.9333 | 0.9591 | 0.2853 | 1.4 |

Severe regressions: 6
No-tool false positives: 0
API_REQUIRED underuse proxy count: 2
Unsupported claims: 0

## Internal 50

| Mode | Overall | Behavior | Final answer | No-tool FP | API underuse | Unsupported | API calls | SQL calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| packaged_baseline_real | 0.6743 | 0.7904 | 0.6325 | 0 | 0 | 0 | 33 | 35 |
| robust_generalized_harness_candidate_v2_real | 0.7843 | 0.8529 | 0.6675 | 0 | 0 | 0 | 26 | 28 |

Helped/hurt/neutral: 11/0/39

## Checkpoint Coverage

- Progressive evidence policy rows: 35/35
- Hybrid answer composer rows: 35/35
- Entry actions: `{'EVIDENCE_PIPELINE': 31, 'SAFE_API_PROBE': 4}`
- Answer intents: `{'STATUS': 4, 'LIST': 18, 'COUNT': 11, 'ERROR_CAVEAT': 2}`
- Answer modes: `{'CANONICAL_DATA': 33, 'CANONICAL_CAVEAT': 2}`
- Selected answer sources: `{'LEGACY_SAFE_RENDERER': 24, 'DETERMINISTIC_FALLBACK': 9, 'HYBRID_CANONICAL_CAVEAT': 1, 'HYBRID_CANONICAL_DATA': 1}`

## Safety And Readiness

- Hardcode/leakage audit unsafe runtime hardcode count: 0
- Fake-score unsafe count: 0
- Score provenance runtime visible evaluator-data count: 0
- SDK direct LLM HTTP hits: 0
- `check_submission_ready.py`: passed
- hidden-style cases: 48
- `git diff --check`: passed

## Remaining Blockers

- Organizer35 answer score and final score still trail SQL_FIRST baseline.
- V2 saves tool calls but regresses API score on 2 organizer rows.
- Structured data rendering needs scorer-aligned tuning before any promotion discussion.

No promotion recommendation.
