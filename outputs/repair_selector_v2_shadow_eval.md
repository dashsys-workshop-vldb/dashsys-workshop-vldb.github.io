# Repair Selector V2 Shadow Eval

- Success: False
- Strictly better selected count: 0
- Repaired worse count: 8
- Safe repaired worse count: 0

| Query ID | Cluster | Score delta | Tool delta | Selected | Failed checks |
| --- | --- | ---: | ---: | --- | --- |
| `example_000` | not_targeted | 0.0 | 0 | repaired |  |
| `example_001` | not_targeted | 0.0 | 0 | repaired |  |
| `example_002` | not_targeted | 0.0 | 0 | repaired |  |
| `example_003` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_004` | zero_score_margin | 0.0 | 0 | repaired |  |
| `example_005` | zero_score_margin | -0.1657 | 0 | current | endpoint_family_confidence, fusion_agreement, safety_verifier, score_regression |
| `example_006` | schema_vs_dataset_confusion | 0.0 | 0 | repaired |  |
| `example_007` | schema_vs_dataset_confusion | 0.1148 | 0 | current | safety_verifier |
| `example_008` | not_targeted | -0.0125 | 1 | current | endpoint_family_confidence, safety_verifier, score_regression, tool_call_increase |
| `example_009` | missing_gold_api_in_top_k | 0.0 | 0 | repaired |  |
| `example_010` | zero_score_margin | -0.1402 | 0 | current | fusion_agreement, safety_verifier, score_regression |
| `example_011` | missing_gold_api_in_top_k | -0.1148 | 0 | current | safety_verifier, score_regression |
| `example_012` | missing_gold_api_in_top_k | -0.1658 | 0 | current | safety_verifier, score_regression |
| `example_013` | missing_gold_api_in_top_k | -0.1487 | 0 | current | safety_verifier, score_regression |
| `example_014` | not_targeted | 0.0 | 0 | current | endpoint_family_confidence, safety_verifier |
| `example_015` | tag_api_confusion | 0.0 | 0 | repaired |  |
| `example_016` | tag_api_confusion | 0.0 | 0 | repaired |  |
| `example_017` | tag_api_confusion | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_018` | zero_score_margin | -0.1913 | 0 | current | fusion_agreement, safety_verifier, score_regression |
| `example_019` | missing_gold_api_in_top_k | 0.0 | 0 | repaired |  |
| `example_020` | broad_domain_api_confusion | 0.0 | 0 | repaired |  |
| `example_021` | missing_gold_api_in_top_k | 0.0 | 0 | repaired |  |
| `example_022` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_023` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_024` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_025` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_026` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_027` | missing_gold_api_in_top_k | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_028` | missing_gold_api_in_top_k | 0.0 | 0 | current | endpoint_family_confidence, safety_verifier |
| `example_029` | missing_gold_api_in_top_k | 0.0 | 0 | current | endpoint_family_confidence |
| `example_030` | zero_score_margin | 0.0 | 0 | current | endpoint_family_confidence |
| `example_031` | batch_endpoint_confusion | 0.0 | 0 | repaired |  |
| `example_032` | batch_endpoint_confusion | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_033` | not_targeted | 0.0 | 0 | current | fusion_agreement, safety_verifier |
| `example_034` | zero_score_margin | -0.425 | 0 | current | endpoint_family_confidence, fusion_agreement, safety_verifier, score_regression |
