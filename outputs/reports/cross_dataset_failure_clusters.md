# Cross-Dataset Failure Clusters

Clusters combine official score-loss rows with generated prompt generality evidence.

| Cluster | Official | Generated | Action |
| --- | ---: | ---: | --- |
| `live_api_blocked` | `34` | `71` | `wait_for_adobe_access` |
| `sql_evidence_answer_omission` | `13` | `41` | `keep_analysis_only` |
| `zero_row_local_sql_unclear` | `4` | `6` | `keep_analysis_only` |
| `dry_run_caveat_dominates_sql_answer` | `8` | `0` | `keep_analysis_only` |
| `route_domain_synonym_mismatch` | `0` | `117` | `manual_review_before_router_change` |
| `answer_intent_mismatch` | `0` | `11` | `manual_review_generated_label_noise` |
| `generated_label_noise` | `0` | `3` | `no_code_change` |
| `unsupported_claim_risk` | `3` | `0` | `guard_in_future_trial_only` |
| `evaluator_sensitive_wording` | `24` | `0` | `avoid_broad_rewrite` |
| `no_local_fix_before_adobe_access` | `0` | `71` | `wait_or_keep_analysis_only` |
