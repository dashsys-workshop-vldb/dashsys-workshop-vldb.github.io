# Research V2 Answer Grounding Eval Summary

Generated: 2026-05-28T16:05:01.137037+00:00

## Implementation

- `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` is explicit-only.
- The packaged default remains `SQL_FIRST_API_VERIFY`.
- V2 uses the generalized planner path, not the SQL_FIRST execution base.
- Broad-aware answer grounding is integrated: broad classifier, answer intent router, canonical/legacy-first structured answers, concept generator, mixed composer, final verifier, and legacy fallback.

## Smoke

| Query | Entry | SQL | API | Broad | Intent / Mode | Source |
|---|---:|---:|---:|---|---|---|
| `research_v2_concept_list_reasons` | LLM_DIRECT | 0 | 0 | CONCEPTUAL_BROAD | CONCEPT / LLM_CONCEPT | HYBRID_LLM_CONCEPT |
| `research_v2_meta_list_schemas` | LLM_DIRECT | 0 | 0 | CONCEPTUAL_BROAD | CONCEPT / LLM_CONCEPT | HYBRID_LLM_CONCEPT |
| `research_v2_inactive_journeys` | EVIDENCE_PIPELINE | 1 | 1 | NOT_BROAD | STATUS / CANONICAL_DATA | LEGACY_SAFE_RENDERER |
| `research_v2_local_schema_count` | EVIDENCE_PIPELINE | 1 | 0 | NOT_BROAD | COUNT / CANONICAL_DATA | HYBRID_CANONICAL_DATA |
| `research_v2_live_schema_count` | EVIDENCE_PIPELINE | 1 | 1 | DATA_BROAD | COUNT / LEGACY_FIRST_DATA | HYBRID_CANONICAL_DATA |
| `research_v2_mixed_inactive_journey` | EVIDENCE_PIPELINE | 1 | 1 | MIXED_BROAD | MIXED / HYBRID_MIXED | HYBRID_MIXED |

## Organizer35

| Strategy | Final | Correctness | SQL | API | Answer | Tool calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6518 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 2.5147 | 791.1429 |
| `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` | 0.6403 | 0.6749 | 0.9333 | 0.9591 | 0.3156 | 1.4 | 2.3279 | 1124.4 |

- Organizer35 final delta: `-0.0115`
- Organizer35 answer delta: `-0.0051`
- Helped/hurt/neutral/severe: `7/21/7/2`
- Progressive/hybrid/broad checkpoint coverage: `35/35`, `35/35`, `35/35`
- Selected answer sources: `{'LEGACY_SAFE_RENDERER': 35}`

## Internal50

| Mode | Overall | Behavior | Final answer | Route | SQL calls | API calls | API underuse | No-tool FP | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `packaged_baseline_real` | 0.7168 | 0.8238 | 0.6525 | 0.8 | 40 | 33 | 0 | 0 | 0 |
| `robust_generalized_harness_candidate_v2_real` | 0.7784 | 0.8525 | 0.675 | 0.88 | 38 | 26 | 0 | 0 | 0 |

- Internal50 overall delta: `0.0616`
- Internal50 helped/hurt/neutral: `8/0/42`
- Internal50 SQL/API call deltas: `-2` / `-7`

## Validation

- Focused tests: `135 passed`.
- Hardcode/runtime audit: unsafe runtime hardcode `0`, unsafe fake score `0`.
- Score provenance audit: runtime gold visible `0`.
- `check_submission_ready.py`: passed.
- Hidden-style eval: `48` cases, failed `0`.
- `git diff --check`: passed.

## Remaining Blockers

- Organizer35 V2 remains below SQL_FIRST by `-0.0115` final score.
- Organizer35 API score delta is `-0.0200`; V2 saved calls but hurt some strict API rows.
- Internal50 is positive, but this is not a promotion basis.

No promotion recommendation.
