# DASHSys Offline Shadow Repair Evaluation

Shadow repair execution is **disabled by default**. This report compares current SQL_FIRST_API_VERIFY plans with candidate-derived repaired plans without changing packaged outputs.

## Paired Shadow Eval Summary

- repaired_better_count: 1
- repaired_equal_count: 26
- repaired_worse_count: 8
- unsafe_repair_count: 35
- safe_repaired_better_count: 0
- safe_repaired_equal_count: 14
- safe_repaired_worse_count: 0
- safe_avg_score_delta: 0.0
- safe_avg_tool_delta: 0.0
- unsafe_avg_score_delta: -0.0595
- unsafe_failure_reason_counts: {'api_validation': 2, 'endpoint_family_confidence': 5, 'fusion_agreement': 14, 'score_regression': 8, 'sql_validation': 2, 'tool_call_increase': 1}
- avg_score_delta: -0.0357
- avg_tool_delta: 0.0286
- avg_runtime_delta: 0.0
- Packaged execution changed: False
- Measured accuracy improvement claimed: False
- Measured efficiency improvement claimed: False
- No behavior-changing flags were enabled in this pass.

| Query ID | Cluster | Current score | Repaired score | Delta | Safe? | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `example_000` | `not_targeted` | 0.6903 | 0.6903 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_001` | `not_targeted` | 0.7902 | 0.7902 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_002` | `not_targeted` | 0.761 | 0.761 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_003` | `missing_gold_api_in_top_k` | 0.7156 | 0.7156 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_004` | `zero_score_margin` | 0.6744 | 0.6744 | 0.0 | False | safe_shadow_tie_keep_disabled |
| `example_005` | `zero_score_margin` | 0.913 | 0.7472 | -0.1658 | False | keep_current_repair_selector_rejected |
| `example_006` | `schema_vs_dataset_confusion` | 0.7272 | 0.7272 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_007` | `schema_vs_dataset_confusion` | 0.6552 | 0.77 | 0.1148 | False | keep_current_repair_selector_rejected |
| `example_008` | `not_targeted` | 0.7027 | 0.6902 | -0.0125 | False | keep_current_repair_selector_rejected |
| `example_009` | `missing_gold_api_in_top_k` | 0.7576 | 0.7576 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_010` | `zero_score_margin` | 0.7898 | 0.6496 | -0.1402 | False | keep_current_repair_selector_rejected |
| `example_011` | `missing_gold_api_in_top_k` | 0.7455 | 0.6307 | -0.1148 | False | keep_current_repair_selector_rejected |
| `example_012` | `missing_gold_api_in_top_k` | 0.7287 | 0.5629 | -0.1658 | False | keep_current_repair_selector_rejected |
| `example_013` | `missing_gold_api_in_top_k` | 0.7149 | 0.5662 | -0.1487 | False | keep_current_repair_selector_rejected |
| `example_014` | `not_targeted` | 0.7654 | 0.7654 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_015` | `tag_api_confusion` | 0.6672 | 0.6672 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_016` | `tag_api_confusion` | 0.6621 | 0.6621 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_017` | `tag_api_confusion` | 0.5292 | 0.5292 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_018` | `zero_score_margin` | 0.6654 | 0.4741 | -0.1913 | False | keep_current_repair_selector_rejected |
| `example_019` | `missing_gold_api_in_top_k` | 0.5344 | 0.5344 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_020` | `broad_domain_api_confusion` | 0.5369 | 0.5369 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_021` | `missing_gold_api_in_top_k` | 0.5394 | 0.5394 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_022` | `missing_gold_api_in_top_k` | 0.5406 | 0.5406 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_023` | `missing_gold_api_in_top_k` | 0.5401 | 0.5401 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_024` | `missing_gold_api_in_top_k` | 0.5361 | 0.5361 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_025` | `missing_gold_api_in_top_k` | 0.5355 | 0.5355 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_026` | `missing_gold_api_in_top_k` | 0.5407 | 0.5407 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_027` | `missing_gold_api_in_top_k` | 0.6017 | 0.6017 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_028` | `missing_gold_api_in_top_k` | 0.5348 | 0.5348 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_029` | `missing_gold_api_in_top_k` | 0.5345 | 0.5345 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_030` | `zero_score_margin` | 0.5308 | 0.5308 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_031` | `batch_endpoint_confusion` | 0.5339 | 0.5339 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_032` | `batch_endpoint_confusion` | 0.6711 | 0.6711 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_033` | `not_targeted` | 0.672 | 0.672 | 0.0 | False | no_op_shadow_tie_keep_current |
| `example_034` | `zero_score_margin` | 0.6621 | 0.2371 | -0.425 | False | keep_current_repair_selector_rejected |

## Cluster Canary Recommendation

| Cluster | Rows | Better | Equal | Worse | Avg score delta | Avg tool delta | Avg token delta | Avg runtime delta | Safe to enable? | Recommended flag | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `zero_score_margin` | 6 | 0 | 2 | 4 | -0.1537 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN` | keep_disabled |
| `missing_gold_api_in_top_k` | 15 | 0 | 12 | 3 | -0.0286 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_MISSING_API_TOPK` | keep_disabled |
| `batch_endpoint_confusion` | 2 | 0 | 2 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION` | keep_disabled |
| `tag_api_confusion` | 3 | 0 | 3 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_TAG_API_CONFUSION` | keep_disabled |
| `schema_vs_dataset_confusion` | 2 | 1 | 1 | 0 | 0.0574 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION` | keep_disabled |
| `broad_domain_api_confusion` | 1 | 0 | 1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `None` | keep_disabled |

## Schema/Dataset Repair Analysis

This focused analysis explains why the positive schema/dataset shadow delta still does not enable repair execution.

| Query ID | Score delta | Failed checks | Failure type | Missing signal | Selector decision |
| --- | ---: | --- | --- | --- | --- |
| `example_006` | 0.0 | none | none | no missing signal | keep_current |
| `example_007` | 0.1148 | api_validation | real_risk | catalog-backed endpoint replacement | keep_current |

## Diagnostic Risk-Based Efficiency Controller

Savings are estimates only. Packaged SQL_FIRST_API_VERIFY execution did not skip modules or change measured runtime/tokens in this pass.

- Risk level distribution: {'low': 2, 'medium': 4, 'high': 29}
- Estimated token savings total: 1584.0
- Estimated runtime savings total ms: 150.0
- Measured efficiency improvement claimed: False

| Query ID | Risk | Accuracy risk | Skipped modules | Token saved estimate | Runtime saved estimate ms |
| --- | --- | --- | --- | ---: | ---: |
| `example_000` | low | low - candidates are separated and schema/API signals are consistent | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_001` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_002` | low | low - candidates are separated and schema/API signals are consistent | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_003` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_004` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |
| `example_005` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |
| `example_006` | high | high - risk_cluster:schema_vs_dataset_confusion | none | 0 | 0 |
| `example_007` | high | high - risk_cluster:schema_vs_dataset_confusion | none | 0 | 0 |
| `example_008` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_009` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_010` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |
| `example_011` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_012` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_013` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_014` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_015` | high | high - risk_cluster:tag_api_confusion | none | 0 | 0 |
| `example_016` | high | high - risk_cluster:tag_api_confusion | none | 0 | 0 |
| `example_017` | high | high - risk_cluster:tag_api_confusion | none | 0 | 0 |
| `example_018` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |
| `example_019` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_020` | high | high - risk_cluster:broad_domain_api_confusion | none | 0 | 0 |
| `example_021` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_022` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_023` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_024` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_025` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_026` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_027` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_028` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_029` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 |
| `example_030` | high | high - low_confidence, zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |
| `example_031` | high | high - risk_cluster:batch_endpoint_confusion | none | 0 | 0 |
| `example_032` | high | high - risk_cluster:batch_endpoint_confusion | none | 0 | 0 |
| `example_033` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 |
| `example_034` | high | high - low_confidence, zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 |

## Schema Context Voting

Schema voting is high-risk diagnostic guidance only and does not alter the executed SQL/API plan.

- Active votes: 29
- Agreements: 29
- Compact context safe count: 29

| Query ID | Active | Agreement | Compact safe? | Fallback reason | Token delta |
| --- | --- | --- | --- | --- | ---: |
| `example_000` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_001` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_002` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_003` | True | True | True | compact and fallback top candidates agree | 1596 |
| `example_004` | True | True | True | compact and fallback top candidates agree | 1060 |
| `example_005` | True | True | True | compact and fallback top candidates agree | 1363 |
| `example_006` | True | True | True | compact and fallback top candidates agree | 1281 |
| `example_007` | True | True | True | compact and fallback top candidates agree | 1156 |
| `example_008` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_009` | True | True | True | compact and fallback top candidates agree | 1095 |
| `example_010` | True | True | True | compact and fallback top candidates agree | 1179 |
| `example_011` | True | True | True | compact and fallback top candidates agree | 1316 |
| `example_012` | True | True | True | compact and fallback top candidates agree | 1498 |
| `example_013` | True | True | True | compact and fallback top candidates agree | 1346 |
| `example_014` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_015` | True | True | True | compact and fallback top candidates agree | 1046 |
| `example_016` | True | True | True | compact and fallback top candidates agree | 1217 |
| `example_017` | True | True | True | compact and fallback top candidates agree | 987 |
| `example_018` | True | True | True | compact and fallback top candidates agree | 1084 |
| `example_019` | True | True | True | compact and fallback top candidates agree | 1280 |
| `example_020` | True | True | True | compact and fallback top candidates agree | 1068 |
| `example_021` | True | True | True | compact and fallback top candidates agree | 1108 |
| `example_022` | True | True | True | compact and fallback top candidates agree | 1187 |
| `example_023` | True | True | True | compact and fallback top candidates agree | 1336 |
| `example_024` | True | True | True | compact and fallback top candidates agree | 1274 |
| `example_025` | True | True | True | compact and fallback top candidates agree | 1345 |
| `example_026` | True | True | True | compact and fallback top candidates agree | 1176 |
| `example_027` | True | True | True | compact and fallback top candidates agree | 1495 |
| `example_028` | True | True | True | compact and fallback top candidates agree | 1350 |
| `example_029` | True | True | True | compact and fallback top candidates agree | 1128 |
| `example_030` | True | True | True | compact and fallback top candidates agree | 839 |
| `example_031` | True | True | True | compact and fallback top candidates agree | 1312 |
| `example_032` | True | True | True | compact and fallback top candidates agree | 1034 |
| `example_033` | False | None | None | schema voting is reserved for high-risk diagnostics | None |
| `example_034` | True | True | True | compact and fallback top candidates agree | 1094 |

## Safety Notes

- Packaged strategy unchanged: True
- Repair execution enabled: False
- No live API evidence is fabricated; dry-run API remains dry-run.
- Canary flags are recommendations only and remain off by default.
