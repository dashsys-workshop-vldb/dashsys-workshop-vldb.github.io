# Objective Answer Grounding Adjudication

Raw organizer-style scores are recorded only as raw_score_only fields and are not used as the objective correctness standard.

## Summary

- generated_at: `2026-06-02T11:56:11.038707+00:00`
- source: `latest local Qwen V2 strict trajectories before objective grounding targeted rerun`
- row_count: `35`
- verdict_counts: `{'PASS': 28, 'FAIL': 4, 'UNCLEAR_NEEDS_MANUAL_REVIEW': 3}`
- final_semantic_gate_failure_root_cause_counts: `{'global_unavailable_with_runtime_facts': 2, 'timeout_or_empty_answer': 1, 'true_missing_required_info': 2, 'claim_extractor_false_positive': 5, 'evidence_shape_not_answer_friendly': 1}`
- unsupported_claim_classification_counts: `{'claim_extractor_false_positive': 3, 'numeric/list marker false positive': 2}`
- raw_scores_are_raw_score_only: `True`

## Rows

| query_id | completed | SQL | API | runtime facts | local facts | live facts | caveat/error only | final gate fails | unsupported | missing | scope | raw answer score only | verdict | root cause | note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| example_000 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.1705 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_001 | True | 2 | 2 | 5 | 1 | 0 | 2 | 1 | 0 | 1 | 0 | 0.1635 | FAIL | global_unavailable_with_runtime_facts | real answer collapsed to global unavailable despite scoped empty/API-error evidence for inactive status |
| example_002 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.111 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_003 | False | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0.0 | UNCLEAR_NEEDS_MANUAL_REVIEW | timeout_or_empty_answer | strict row timed out at dependency resolution |
| example_004 | True | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.2 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_005 | True | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0.2795 | FAIL | true_missing_required_info | answer does not include all requested destination columns; unsupported interval 0 was also a false-positive count |
| example_006 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0.0765 | PASS | claim_extractor_false_positive | answer includes scoped local count 0; gate missed sentence-final zero before this fix |
| example_007 | True | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0.2094 | PASS | claim_extractor_false_positive | scoped no-match answer is grounded for empty local evidence; gate incorrectly required prompt filter entity name as result |
| example_008 | True | 1 | 1 | 3 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0.3607 | PASS | gold_wording_mismatch_only | answer is scoped local evidence plus API caveat after repair; initial scope gate was conservative |
| example_009 | True | 1 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.2593 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_010 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0.14 | PASS | claim_extractor_false_positive | final answer is a count answer and final gate passed after repair path |
| example_011 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.3069 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_012 | True | 3 | 1 | 4 | 2 | 0 | 1 | 1 | 1 | 0 | 0 | 0.2424 | UNCLEAR_NEEDS_MANUAL_REVIEW | claim_extractor_false_positive | answer lists runtime audience evidence; unsupported count appears tied to prompt time window or numeric entity text |
| example_013 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0571 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_014 | True | 0 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0.3322 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_015 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.3282 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_016 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.3336 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_017 | True | 0 | 2 | 2 | 0 | 0 | 2 | 1 | 0 | 1 | 0 | 0.0796 | PASS | claim_extractor_false_positive | unavailable answer is appropriate when tag API evidence is unavailable; prompt filter value was treated as missing result info |
| example_018 | True | 0 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0.3077 | PASS | claim_extractor_false_positive | unavailable answer is appropriate when tag detail evidence is unavailable; prompt entity was treated as missing result info |
| example_019 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0648 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_020 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0985 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_021 | True | 1 | 1 | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0.0889 | FAIL | true_missing_required_info | answer uses local segment-like evidence and does not answer default merge policy request |
| example_022 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0809 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_023 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.063 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_024 | True | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0.1815 | UNCLEAR_NEEDS_MANUAL_REVIEW | evidence_shape_not_answer_friendly | runtime dates/examples exist but answer may not identify the actual most-recent updated segment definitions clearly |
| example_025 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0693 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_026 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.08 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_027 | True | 0 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0.2114 | PASS | claim_extractor_false_positive | unavailable answer is appropriate when queued segment-job evidence is unavailable; status filter was treated as required returned status |
| example_028 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0827 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_029 | True | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0925 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_030 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0.1614 | PASS | claim_extractor_false_positive | final answer is scoped local evidence; unsupported decimal-like span was a narrow extractor issue |
| example_031 | True | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.085 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_032 | True | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0.207 | PASS | gold_wording_mismatch_only | final answer is grounded or unavailable with no detected objective grounding issue |
| example_033 | True | 1 | 1 | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0.3166 | FAIL | global_unavailable_with_runtime_facts | answer says globally unavailable despite local zero-count evidence and API caveat |
| example_034 | True | 1 | 2 | 3 | 1 | 0 | 2 | 0 | 1 | 0 | 0 | 0.3673 | PASS | claim_extractor_false_positive | answer is scoped local zero count plus API caveat; unsupported 90 was the prompt time window |

## Final Semantic Gate Failure Categories

- claim_extractor_false_positive: `5`
- evidence_shape_not_answer_friendly: `1`
- global_unavailable_with_runtime_facts: `2`
- timeout_or_empty_answer: `1`
- true_missing_required_info: `2`

## Unsupported Claim Classifications

- claim_extractor_false_positive: `3`
- numeric/list marker false positive: `2`
