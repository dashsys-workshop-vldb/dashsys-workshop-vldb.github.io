# DASHSys Offline Shadow Repair Evaluation

Shadow repair execution is **disabled by default**. This report compares current SQL_FIRST_API_VERIFY plans with candidate-derived repaired plans without changing packaged outputs.

## Paired Shadow Eval Summary

- repaired_better_count: 1
- repaired_equal_count: 26
- repaired_worse_count: 8
- unsafe_repair_count: 21
- avg_score_delta: -0.0357
- avg_tool_delta: 0.0286
- avg_runtime_delta: 0.0

| Query ID | Cluster | Current score | Repaired score | Delta | Safe? | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `example_000` | `not_targeted` | 0.6903 | 0.6903 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_001` | `not_targeted` | 0.7902 | 0.7902 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_002` | `not_targeted` | 0.761 | 0.761 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_003` | `missing_gold_api_in_top_k` | 0.7156 | 0.7156 | 0.0 | False | reject_unsafe_repair |
| `example_004` | `zero_score_margin` | 0.6744 | 0.6744 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_005` | `zero_score_margin` | 0.913 | 0.7472 | -0.1658 | False | reject_unsafe_repair |
| `example_006` | `schema_vs_dataset_confusion` | 0.7272 | 0.7272 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_007` | `schema_vs_dataset_confusion` | 0.6552 | 0.77 | 0.1148 | False | reject_unsafe_repair |
| `example_008` | `not_targeted` | 0.7027 | 0.6902 | -0.0125 | False | reject_unsafe_repair |
| `example_009` | `missing_gold_api_in_top_k` | 0.7576 | 0.7576 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_010` | `zero_score_margin` | 0.7898 | 0.6496 | -0.1402 | False | reject_unsafe_repair |
| `example_011` | `missing_gold_api_in_top_k` | 0.7455 | 0.6307 | -0.1148 | False | reject_score_regression |
| `example_012` | `missing_gold_api_in_top_k` | 0.7287 | 0.5629 | -0.1658 | False | reject_unsafe_repair |
| `example_013` | `missing_gold_api_in_top_k` | 0.7149 | 0.5662 | -0.1487 | False | reject_unsafe_repair |
| `example_014` | `not_targeted` | 0.7654 | 0.7654 | 0.0 | False | reject_unsafe_repair |
| `example_015` | `tag_api_confusion` | 0.6672 | 0.6672 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_016` | `tag_api_confusion` | 0.6621 | 0.6621 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_017` | `tag_api_confusion` | 0.5292 | 0.5292 | 0.0 | False | reject_unsafe_repair |
| `example_018` | `zero_score_margin` | 0.6654 | 0.4741 | -0.1913 | False | reject_unsafe_repair |
| `example_019` | `missing_gold_api_in_top_k` | 0.5344 | 0.5344 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_020` | `broad_domain_api_confusion` | 0.5369 | 0.5369 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_021` | `missing_gold_api_in_top_k` | 0.5394 | 0.5394 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_022` | `missing_gold_api_in_top_k` | 0.5406 | 0.5406 | 0.0 | False | reject_unsafe_repair |
| `example_023` | `missing_gold_api_in_top_k` | 0.5401 | 0.5401 | 0.0 | False | reject_unsafe_repair |
| `example_024` | `missing_gold_api_in_top_k` | 0.5361 | 0.5361 | 0.0 | False | reject_unsafe_repair |
| `example_025` | `missing_gold_api_in_top_k` | 0.5355 | 0.5355 | 0.0 | False | reject_unsafe_repair |
| `example_026` | `missing_gold_api_in_top_k` | 0.5407 | 0.5407 | 0.0 | False | reject_unsafe_repair |
| `example_027` | `missing_gold_api_in_top_k` | 0.6017 | 0.6017 | 0.0 | False | reject_unsafe_repair |
| `example_028` | `missing_gold_api_in_top_k` | 0.5348 | 0.5348 | 0.0 | False | reject_unsafe_repair |
| `example_029` | `missing_gold_api_in_top_k` | 0.5345 | 0.5345 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_030` | `zero_score_margin` | 0.5308 | 0.5308 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_031` | `batch_endpoint_confusion` | 0.5339 | 0.5339 | 0.0 | True | safe_shadow_tie_recommend_canary |
| `example_032` | `batch_endpoint_confusion` | 0.6711 | 0.6711 | 0.0 | False | reject_unsafe_repair |
| `example_033` | `not_targeted` | 0.672 | 0.672 | 0.0 | False | reject_unsafe_repair |
| `example_034` | `zero_score_margin` | 0.6621 | 0.2371 | -0.425 | False | reject_unsafe_repair |

## Cluster Canary Recommendation

| Cluster | Rows | Better | Equal | Worse | Avg score delta | Avg tool delta | Avg token delta | Avg runtime delta | Safe to enable? | Recommended flag | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `zero_score_margin` | 6 | 0 | 2 | 4 | -0.1537 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN` | keep_disabled |
| `missing_gold_api_in_top_k` | 15 | 0 | 12 | 3 | -0.0286 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_MISSING_API_TOPK` | keep_disabled |
| `batch_endpoint_confusion` | 2 | 0 | 2 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION` | keep_disabled |
| `tag_api_confusion` | 3 | 0 | 3 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_TAG_API_CONFUSION` | keep_disabled |
| `schema_vs_dataset_confusion` | 2 | 1 | 1 | 0 | 0.0574 | 0.0 | 0.0 | 0.0 | False | `ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION` | keep_disabled |
| `broad_domain_api_confusion` | 1 | 0 | 1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | `None` | keep_disabled |

## Safety Notes

- Packaged strategy unchanged: True
- Repair execution enabled: False
- No live API evidence is fabricated; dry-run API remains dry-run.
- Canary flags are recommendations only and remain off by default.
