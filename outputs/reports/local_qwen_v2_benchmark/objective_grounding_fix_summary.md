# Objective Grounding Fix Summary

## Executive Summary

Targeted answer-grounding fixes were implemented for objective verifier noise and scoped zero-row evidence handling. The local Qwen V2 smoke passed 7/7 with zero unsupported claims, zero no-tool false positives, and zero final semantic gate failures.

Strict V2 dev eval completed all 35 rows with one contained timeout (`example_003`). Raw organizer-style scores still trail packaged SQL_FIRST substantially and are recorded as raw_score_only, not as semantic truth. V2 remains safe to keep/commit as shadow research code, but not safe to promote.

## Files Changed

- `dashagent/final_answer_claim_extractor.py`
- `dashagent/llm_final_answer_composer.py`
- `tests/test_llm_final_answer_composer.py`
- Reports under `outputs/reports/local_qwen_v2_benchmark/`

## Fixes Applied

- Count claim extractor ignores prompt time windows such as last 90 days.
- Count claim extractor ignores interval values such as interval of 0.
- Safe fallback treats local zero-row SQL evidence as scoped runtime evidence instead of global unavailable.
- Semantic gate allows scoped no-match wording for empty local filtered list evidence.
- Numeric value matching accepts sentence-final values such as 0. without matching decimal values such as 0.026.

## Smoke Result

- row_count: `7`
- passed_count: `7`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_final_failures: `0`
- runtime_fact_count: `8`
- raw_sql_fallback_used_count: `0`

## Strict Dev Eval Raw Score Comparison

Raw-score-only; not used as objective correctness proof.

| Strategy | Final | Correctness | Answer | SQL | API | Tool Calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6563 | 0.6812 | 0.3223 | 0.9333 | 0.9791 | 1.4571 | 0.0176 | 796.8571 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 | 0.2074 | 0.2677 | 0.1858 | 0.0000 | 0.4537 | 1.3714 | 14.2209 | 2084.8000 |

## V2 Eval Counters

- row_count: `35`
- timeout_count: `1`
- timeout_query_ids: `['example_003']`
- failed_query_ids: `['example_003']`
- sql_calls: `23`
- api_calls: `25`
- tool_calls: `48`
- runtime_fact_count_approx_successful_tool_steps: `22`
- runtime_fact_count_approx_rows_or_successful_calls: `74`
- raw_sql_fallback_used_count_from_checkpoints: `0`

## Post-Fix Semantic Gate Failures

- Final semantic gate failures excluding timeout: `8`
- Failure counts: `{'missing_required_info': 6, 'contradiction': 1, 'scope_error': 1}`
- Objective real unsupported claims: `0`
- Claim-extractor false positives after fix: `1`

| Query | Error Type | Short Finding |
|---|---|---|
| example_001 | missing_required_info | missing ['status'] |
| example_004 | contradiction | unsupported gate claim |
| example_012 | scope_error | scope/other |
| example_017 | missing_required_info | missing ['entity_names'] |
| example_018 | missing_required_info | missing ['entity_names'] |
| example_021 | missing_required_info | missing ['entity_names'] |
| example_024 | missing_required_info | missing ['entity_names'] |
| example_027 | missing_required_info | missing ['entity_names'] |

## Objective Adjudication

- Verdict counts: `{'PASS': 26, 'FAIL': 4, 'UNCLEAR_TIMEOUT': 1, 'SAFE_CAVEAT_ONLY': 3, 'PASS_WITH_VERIFIER_FALSE_POSITIVE': 1}`
- Root cause counts: `{'semantic_gate_passed_or_no_objective_issue': 26, 'true_missing_or_wrong_required_data': 1, 'timeout': 1, 'wrong_status_or_object_scope': 1, 'incomplete_relationship_filter': 1, 'api_unavailable_caveat': 3, 'missing_default_merge_policy_filter': 1, 'answer_contains_entities_and_dates': 1}`

| Query | Verdict | Root Cause | Note |
|---|---|---|---|
| example_001 | FAIL | true_missing_or_wrong_required_data | Returned 0 inactive journeys with API caveat; prompt required inactive journeys and evidence path selected wrong/incomplete data. |
| example_003 | UNCLEAR_TIMEOUT | timeout | Per-query timeout at dependency resolution; no fresh final answer evidence. |
| example_004 | FAIL | wrong_status_or_object_scope | Asked for failed dataflow run IDs; answer includes enabled status/name examples, so object/status grounding remains suspect. |
| example_006 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |
| example_007 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |
| example_010 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |
| example_012 | FAIL | incomplete_relationship_filter | Answer lists segments/target/mapping evidence but does not cleanly answer audiences mapped to new destinations in last 3 months. |
| example_017 | SAFE_CAVEAT_ONLY | api_unavailable_caveat | API evidence unavailable; no unsupported data claim, but answer is low-information. |
| example_018 | SAFE_CAVEAT_ONLY | api_unavailable_caveat | API evidence unavailable; no unsupported data claim, but answer is low-information. |
| example_021 | FAIL | missing_default_merge_policy_filter | Answer lists merge-policy-like rows but does not establish default policy for the requested schema class. |
| example_024 | PASS_WITH_VERIFIER_FALSE_POSITIVE | answer_contains_entities_and_dates | Answer provides recent segment definition examples and dates; semantic gate still flags entity_names too strictly. |
| example_027 | SAFE_CAVEAT_ONLY | api_unavailable_caveat | API evidence unavailable for segment jobs; no unsupported data claim, but answer is low-information. |
| example_030 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |
| example_033 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |
| example_034 | PASS | semantic_gate_passed_or_no_objective_issue | Previously noisy/failing grounding case now passes or is materially improved by the targeted fix. |

## Gates And Validation

- Semantic route promotion gate: promotion_allowed=`False`, recommendation=`keep_shadow_only`
- Integrated robustness gate: promotion_allowed=`True`, recommendation=`promote_efficiency_recovery_fix`
- Hidden style: `{'failed_cases': 0, 'family_stability_rate': 1.0, 'passed_cases': 48, 'schema_stability_rate': 1.0, 'top_failure_categories': [], 'total_cases': 48}`
- SDK usage audit runtime_llm_direct_http_hits: `0`
- Focused tests: `106 passed`
- Full pytest: `1176 passed, 1 skipped`
- check_submission_ready: `ok=true`; packaged default remains `SQL_FIRST_API_VERIFY`; secret scan ok
- git diff --check: passed

## Recommendation

Safe to keep and safe to commit as a narrow answer-grounding hardening patch. Not safe to promote V2: strict V2 still has one timeout and residual objective grounding failures. Keep `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` shadow-only.
