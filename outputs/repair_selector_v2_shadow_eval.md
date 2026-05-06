# Repair Selector V2 Shadow Eval

- Success: False
- Strictly better selected count: 0
- No-op ties kept current: 25
- Score ties kept current: 1
- Repaired worse count: 8
- Safe repaired worse count: 0

| Query ID | Cluster | Score delta | Tool delta | Selected | Decision | Failed checks |
| --- | --- | ---: | ---: | --- | --- | --- |
| `example_000` | not_targeted | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_001` | not_targeted | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_002` | not_targeted | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_003` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_004` | zero_score_margin | 0.0 | 0 | current | score_tie_keep_current |  |
| `example_005` | zero_score_margin | -0.1657 | 0 | current | keep_current_failed_gates | endpoint_family_confidence, fusion_agreement, safety_verifier, score_regression |
| `example_006` | schema_vs_dataset_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_007` | schema_vs_dataset_confusion | 0.1148 | 0 | current | keep_current_failed_gates | safety_verifier |
| `example_008` | not_targeted | -0.0125 | 1 | current | keep_current_failed_gates | endpoint_family_confidence, safety_verifier, score_regression, tool_call_increase |
| `example_009` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_010` | zero_score_margin | -0.1402 | 0 | current | keep_current_failed_gates | fusion_agreement, safety_verifier, score_regression |
| `example_011` | missing_gold_api_in_top_k | -0.1148 | 0 | current | keep_current_failed_gates | safety_verifier, score_regression |
| `example_012` | missing_gold_api_in_top_k | -0.1658 | 0 | current | keep_current_failed_gates | safety_verifier, score_regression |
| `example_013` | missing_gold_api_in_top_k | -0.1487 | 0 | current | keep_current_failed_gates | safety_verifier, score_regression |
| `example_014` | not_targeted | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_015` | tag_api_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_016` | tag_api_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_017` | tag_api_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_018` | zero_score_margin | -0.1913 | 0 | current | keep_current_failed_gates | fusion_agreement, safety_verifier, score_regression |
| `example_019` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_020` | broad_domain_api_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_021` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_022` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_023` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_024` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_025` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_026` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_027` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_028` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_029` | missing_gold_api_in_top_k | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_030` | zero_score_margin | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_031` | batch_endpoint_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_032` | batch_endpoint_confusion | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_033` | not_targeted | 0.0 | 0 | current | no_op_tie_keep_current |  |
| `example_034` | zero_score_margin | -0.425 | 0 | current | keep_current_failed_gates | endpoint_family_confidence, fusion_agreement, safety_verifier, score_regression |
