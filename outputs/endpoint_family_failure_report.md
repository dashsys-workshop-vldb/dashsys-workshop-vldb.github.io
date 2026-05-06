# Endpoint-Family Failure Report

- Risky rows: 35
- Failure types: {'low_confidence_or_broad_domain': 10, 'gold_api_missing_from_top_k': 7, 'executed_endpoint_family_differs_from_ranked_family': 17, 'zero_candidate_score_margin': 1}

| Query ID | Cluster | Family | Confidence | Failure type | Suggested non-gold improvement |
| --- | --- | --- | ---: | --- | --- |
| `example_000` | broad_domain_api_confusion | journey_list | 1.0 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_001` | broad_domain_api_confusion | journey_list | 1.0 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_002` | broad_domain_api_confusion | journey_list | 1.0 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_003` | missing_gold_api_in_top_k | segment_definitions | 1.0 | gold_api_missing_from_top_k | Add endpoint-family coverage diagnostics for catalog-backed families with low top-k recall. |
| `example_004` | zero_score_margin | flow_runs | 1.0 | executed_endpoint_family_differs_from_ranked_family | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
| `example_005` | zero_score_margin | None | 0.0 | executed_endpoint_family_differs_from_ranked_family | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
| `example_006` | schema_vs_dataset_confusion | dataset_list | 0.8825 | low_confidence_or_broad_domain | Clarify schema detail versus dataset list intent using schema-dataset relation vocabulary. |
| `example_007` | schema_vs_dataset_confusion | schema_detail | 0.94 | executed_endpoint_family_differs_from_ranked_family | Clarify schema detail versus dataset list intent using schema-dataset relation vocabulary. |
| `example_008` | broad_domain_api_confusion | None | 0.0 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_009` | broad_domain_api_confusion | schema_list | 0.865 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_010` | zero_score_margin | schema_list | 0.97 | zero_candidate_score_margin | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
| `example_011` | broad_domain_api_confusion | schema_list | 0.97 | low_confidence_or_broad_domain | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_012` | missing_gold_api_in_top_k | segment_definitions | 1.0 | gold_api_missing_from_top_k | Add endpoint-family coverage diagnostics for catalog-backed families with low top-k recall. |
| `example_013` | broad_domain_api_confusion | dataset_list | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_014` | broad_domain_api_confusion | audit_events | 0.7425 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_015` | tag_api_confusion | tag_list | 1.0 | low_confidence_or_broad_domain | Separate tag list/detail/category vocabulary using endpoint catalog path shapes. |
| `example_016` | tag_api_confusion | tag_list | 1.0 | low_confidence_or_broad_domain | Separate tag list/detail/category vocabulary using endpoint catalog path shapes. |
| `example_017` | tag_api_confusion | tag_list | 0.89 | low_confidence_or_broad_domain | Separate tag list/detail/category vocabulary using endpoint catalog path shapes. |
| `example_018` | zero_score_margin | tag_list | 0.92 | gold_api_missing_from_top_k | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
| `example_019` | broad_domain_api_confusion | merge_policies | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_020` | broad_domain_api_confusion | merge_policies | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_021` | broad_domain_api_confusion | merge_policies | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_022` | broad_domain_api_confusion | segment_definitions | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_023` | broad_domain_api_confusion | segment_definitions | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_024` | broad_domain_api_confusion | segment_definitions | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_025` | broad_domain_api_confusion | segment_jobs | 0.9725 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_026` | broad_domain_api_confusion | segment_jobs | 0.9725 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_027` | broad_domain_api_confusion | segment_jobs | 0.9725 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_028` | broad_domain_api_confusion | batch_list | 0.74 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_029` | broad_domain_api_confusion | batch_list | 0.8075 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_030` | zero_score_margin | batch_details | 0.8075 | gold_api_missing_from_top_k | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
| `example_031` | missing_gold_api_in_top_k | batch_files | 1.0 | gold_api_missing_from_top_k | Add endpoint-family coverage diagnostics for catalog-backed families with low top-k recall. |
| `example_032` | missing_gold_api_in_top_k | batch_failed_files | 1.0 | gold_api_missing_from_top_k | Add endpoint-family coverage diagnostics for catalog-backed families with low top-k recall. |
| `example_033` | broad_domain_api_confusion | observability_metrics | 1.0 | executed_endpoint_family_differs_from_ranked_family | Route broad platform questions through domain vocabulary before endpoint-specific boosts. |
| `example_034` | zero_score_margin | None | 0.0 | gold_api_missing_from_top_k | Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence. |
