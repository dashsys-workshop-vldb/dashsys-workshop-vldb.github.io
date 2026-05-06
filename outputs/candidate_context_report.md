# Candidate Context Report

Candidate context is schema/API retrieval only. It does not use public gold patterns or decide final SQL.

## Summary

| Metric | Value |
| --- | ---: |
| avg_candidate_context_tokens | 4301.4 |
| avg_full_schema_context_tokens | 4682 |
| compression_ratio | 0.9187 |
| table_recall_at_3 | 0.7778 |
| table_recall_at_5 | 0.9333 |
| api_recall_at_3 | 0.7581 |
| api_recall_at_5 | 0.7903 |
| candidate_low_confidence_count | 2 |
| candidate_zero_margin_count | 6 |
| percent_low_confidence | 0.0571 |
| percent_zero_margin | 0.1714 |
| recommended_fallback_rate | 0.1714 |
| context_mode_distribution | {'candidate': 18, 'expanded_candidate': 11, 'hybrid': 6} |
| avg_forward_link_count | 34.0286 |
| avg_backward_link_count | 1.2 |
| structural_join_preserved_count | 35 |
| schema_link_risk_distribution | {'low': 29, 'medium': 6} |
| cluster_gate_status | retrieval-cluster improvement measured |
| risk_level_distribution | {'low': 2, 'medium': 5, 'high': 28} |
| estimated_token_savings_total | 1848.0 |
| estimated_runtime_savings_ms_total | 175.0 |
| estimated_savings_label | estimated only - packaged execution did not skip modules |
| schema_vote_active_count | 28 |
| schema_vote_agreement_count | 28 |
| compact_context_safe_count | 28 |

## Candidate Miss Analysis

| Query ID | Missing tables | Missing APIs | Confidence | Margin | Recommended mode |
| --- | --- | --- | ---: | ---: | --- |
| `example_003` |  | /data/foundation/flowservice/flows | 1.0 | 0.165 | candidate |
| `example_004` |  |  | 0.72 | 0.0 | hybrid |
| `example_005` |  |  | 0.6 | 0.0 | hybrid |
| `example_006` |  |  | 0.9246 | 0.41 | candidate |
| `example_007` | hkg_br_blueprint_collection |  | 0.8635 | 0.92 | candidate |
| `example_009` |  |  | 0.8438 | 0.7 | candidate |
| `example_010` |  |  | 0.5164 | 0.0 | hybrid |
| `example_012` | dim_segment | /data/foundation/audit/events | 0.758 | 0.19 | candidate |
| `example_013` |  |  | 0.9387 | 0.41 | candidate |
| `example_018` |  | /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818 | 0.6471 | 0.0 | hybrid |
| `example_030` |  | /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F | 0.2636 | 0.0 | hybrid |
| `example_031` |  | /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 0.758 | 0.19 | candidate |
| `example_032` |  | /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed | 0.47 | 0.15 | expanded_candidate |
| `example_034` |  | /data/infrastructure/observability/insights/metrics | 0.33 | 0.0 | hybrid |

## Candidate Risk Clusters

These clusters compare baseline retrieval ordering with the ranking/report-only ordering. They do not change executed SQL/API plans or answer behavior.

| Cluster | Before | After | Delta | Improved? | Example query IDs | Diagnostic only | Behavior changing? | Likely safe improvement |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `zero_score_margin` | 32 | 6 | -26 | True | example_004, example_005, example_010, example_018, example_030, example_034 | True | False | Improve tie-break diagnostics or fall back to hybrid/full schema context; do not force a table choice from a tied score. |
| `low_confidence` | 14 | 2 | -12 | True | example_030, example_034 | True | False | Use broader context and surface the uncertainty to LLM/controller paths instead of narrowing aggressively. |
| `missing_gold_table_in_top_k` | 4 | 2 | -2 | True | example_007, example_012 | True | False | Audit schema aliases and structural bridge coverage using schema-level signals only. |
| `missing_gold_api_in_top_k` | 15 | 7 | -8 | True | example_003, example_012, example_018, example_030, example_031, example_032, example_034 | True | False | Improve endpoint catalog descriptions and API-family aliases without using public answer patterns. |
| `broad_domain_api_confusion` | 4 | 1 | -3 | True | example_012 | True | False | Add endpoint-family labels and confidence diagnostics for broad platform/API intents. |
| `schema_vs_dataset_confusion` | 4 | 0 | -4 | True |  | True | False | Clarify schema-vs-dataset table/API affordances in retrieval-only metadata. |
| `tag_api_confusion` | 4 | 1 | -3 | True | example_018 | True | False | Strengthen tag endpoint summaries and keep dry-run API evidence labeled separately. |
| `batch_endpoint_confusion` | 8 | 5 | -3 | True | example_003, example_030, example_031, example_032, example_034 | True | False | Audit batch endpoint family labels and alias repair diagnostics. |

## Cluster Gate

- Status: retrieval-cluster improvement measured
- Passed: True
- Improved target clusters: zero_score_margin, missing_gold_api_in_top_k, batch_endpoint_confusion, tag_api_confusion, schema_vs_dataset_confusion
- No score claim: ranking-only changes are reported as retrieval diagnostics unless strict-score improvement is measured.

## Shadow Repair Evaluation Linkage

- Shadow repair eval available: True
- Repair execution enabled: False
- Canary recommendations are offline what-if diagnostics and do not change SQL_FIRST_API_VERIFY execution.

| Cluster | Rows | Better | Equal | Worse | Safe to enable? | Recommended flag |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `batch_endpoint_confusion` | 2 | 0 | 2 | 0 | False | `ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION` |
| `broad_domain_api_confusion` | 1 | 0 | 1 | 0 | False | `None` |
| `missing_gold_api_in_top_k` | 15 | 0 | 12 | 3 | False | `ENABLE_REPAIR_FOR_MISSING_API_TOPK` |
| `schema_vs_dataset_confusion` | 2 | 1 | 1 | 0 | False | `ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION` |
| `tag_api_confusion` | 3 | 0 | 3 | 0 | False | `ENABLE_REPAIR_FOR_TAG_API_CONFUSION` |
| `zero_score_margin` | 6 | 0 | 2 | 4 | False | `ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN` |

## Risk-Based Efficiency Controller

This section is diagnostic only. Token/runtime savings are estimates from module policy and are not measured efficiency gains because packaged execution is unchanged.

| Query ID | Risk level | Accuracy risk | Skipped modules | Token saved estimate | Runtime saved estimate ms | Estimated only? |
| --- | --- | --- | --- | ---: | ---: | --- |
| `example_000` | low | low - candidates are separated and schema/API signals are consistent | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_001` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_002` | low | low - candidates are separated and schema/API signals are consistent | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_003` | high | high - risk_cluster:missing_gold_api_in_top_k, missing_candidate_apis | none | 0 | 0 | True |
| `example_004` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 | True |
| `example_005` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 | True |
| `example_006` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_007` | high | high - risk_cluster:missing_gold_api_in_top_k, missing_candidate_tables | none | 0 | 0 | True |
| `example_008` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_009` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_010` | high | high - zero_score_margin, risk_cluster:zero_score_margin | none | 0 | 0 | True |
| `example_011` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_012` | high | high - risk_cluster:missing_gold_api_in_top_k, missing_candidate_tables, missing_candidate_apis | none | 0 | 0 | True |
| `example_013` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_014` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_015` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_016` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_017` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_018` | high | high - zero_score_margin, risk_cluster:zero_score_margin, missing_candidate_apis | none | 0 | 0 | True |
| `example_019` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_020` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_021` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_022` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_023` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_024` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_025` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_026` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_027` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_028` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_029` | high | high - risk_cluster:missing_gold_api_in_top_k | none | 0 | 0 | True |
| `example_030` | high | high - low_confidence, zero_score_margin, risk_cluster:zero_score_margin, missing_candidate_apis | none | 0 | 0 | True |
| `example_031` | high | high - risk_cluster:missing_gold_api_in_top_k, missing_candidate_apis | none | 0 | 0 | True |
| `example_032` | high | high - risk_cluster:missing_gold_api_in_top_k, missing_candidate_apis | none | 0 | 0 | True |
| `example_033` | medium | medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 264 | 25.0 | True |
| `example_034` | high | high - low_confidence, zero_score_margin, risk_cluster:zero_score_margin, missing_candidate_apis | none | 0 | 0 | True |

## Schema Context Voting

Schema voting compares compact candidate context against broader hybrid/full context for high-risk diagnostics only; it does not change executed SQL/API plans.

| Query ID | Active | Agreement | Compact safe? | Fallback reason | Token delta | Compact tables | Fallback tables |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `example_000` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_001` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_002` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_003` | True | True | True | compact and fallback top candidates agree | 1596 | dim_segment, dim_collection, dim_target, hkg_br_segment_target | dim_segment, dim_collection, dim_target, hkg_br_segment_target |
| `example_004` | True | True | True | compact and fallback top candidates agree | 1060 | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_005` | True | True | True | compact and fallback top candidates agree | 1363 | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_base_segment_used_by_dependent_segment, dim_connector, dim_target, br_campaign_segment |
| `example_006` | True | True | True | compact and fallback top candidates agree | 1281 | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection |
| `example_007` | True | True | True | compact and fallback top candidates agree | 1156 | dim_blueprint, dim_segment, br_campaign_segment, dim_collection | dim_blueprint, hkg_br_base_segment_used_by_dependent_segment, dim_segment, br_campaign_segment |
| `example_008` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_009` | True | True | True | compact and fallback top candidates agree | 1095 | dim_blueprint, hkg_br_blueprint_collection, dim_collection, hkg_br_blueprint_property | dim_blueprint, hkg_br_blueprint_collection, dim_collection, hkg_br_blueprint_property |
| `example_010` | True | True | True | compact and fallback top candidates agree | 1179 | dim_blueprint, dim_collection, dim_segment, br_campaign_segment | dim_blueprint, dim_collection, dim_segment, br_campaign_segment |
| `example_011` | True | True | True | compact and fallback top candidates agree | 1316 | hkg_br_blueprint_collection, dim_blueprint, dim_collection, br_campaign_segment | hkg_br_blueprint_collection, dim_blueprint, dim_collection, br_campaign_segment |
| `example_012` | True | True | True | compact and fallback top candidates agree | 1498 | dim_target, hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_connector | dim_target, hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_connector |
| `example_013` | True | True | True | compact and fallback top candidates agree | 1346 | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection |
| `example_014` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_015` | True | True | True | compact and fallback top candidates agree | 1046 | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment | hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_blueprint, dim_campaign |
| `example_016` | True | True | True | compact and fallback top candidates agree | 1217 | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment | hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_blueprint, dim_campaign |
| `example_017` | True | True | True | compact and fallback top candidates agree | 987 | dim_connector, dim_blueprint, dim_collection, br_campaign_segment | dim_connector, dim_blueprint, dim_collection, br_campaign_segment |
| `example_018` | True | True | True | compact and fallback top candidates agree | 1084 | br_campaign_segment, hkg_br_collection_segment, hkg_br_segment_property, hkg_br_segment_target | hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_segment_property, hkg_br_segment_target |
| `example_019` | True | True | True | compact and fallback top candidates agree | 1280 | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment | hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_blueprint, dim_campaign |
| `example_020` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_021` | True | True | True | compact and fallback top candidates agree | 1108 | dim_blueprint, dim_segment, br_campaign_segment, hkg_br_blueprint_property | dim_blueprint, dim_segment, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment |
| `example_022` | True | True | True | compact and fallback top candidates agree | 1187 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_023` | True | True | True | compact and fallback top candidates agree | 1336 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_024` | True | True | True | compact and fallback top candidates agree | 1274 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_025` | True | True | True | compact and fallback top candidates agree | 1345 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_026` | True | True | True | compact and fallback top candidates agree | 1176 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_027` | True | True | True | compact and fallback top candidates agree | 1495 | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment |
| `example_028` | True | True | True | compact and fallback top candidates agree | 1350 | dim_collection, dim_segment, hkg_br_segment_target, dim_blueprint | dim_collection, dim_segment, hkg_br_segment_target, dim_blueprint |
| `example_029` | True | True | True | compact and fallback top candidates agree | 1128 | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property | dim_campaign, dim_segment, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment |
| `example_030` | True | True | True | compact and fallback top candidates agree | 839 | br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property, hkg_br_collection_segment | br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection, hkg_br_blueprint_property |
| `example_031` | True | True | True | compact and fallback top candidates agree | 1312 | dim_segment, hkg_br_blueprint_collection, dim_collection, dim_blueprint | dim_segment, hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_collection |
| `example_032` | True | True | True | compact and fallback top candidates agree | 1034 | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property | dim_campaign, dim_segment, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment |
| `example_033` | False | None | None | schema voting is reserved for high-risk diagnostics | None |  |  |
| `example_034` | True | True | True | compact and fallback top candidates agree | 1094 | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property | dim_campaign, dim_segment, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment |

## Curated Join Hint Audit

Used gold patterns: False

| Left | Right | Source | Reason |
| --- | --- | --- | --- |
| dim_campaign.CAMPAIGNID | br_campaign_segment.CAMPAIGNID | manual general rule | Curated: Campaign to segment bridge. |
| dim_segment.SEGMENTID | br_campaign_segment.SEGMENTID | manual general rule | Curated: Campaign to segment bridge. |
| dim_segment.SEGMENTID | hkg_br_segment_target.SEGMENTID | manual general rule | Curated: Segment to target bridge. |
| dim_target.TARGETID | hkg_br_segment_target.TARGETID | manual general rule | Curated: Segment to target bridge. |
| br_campaign_segment.SEGMENTID | dim_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| br_campaign_segment.SEGMENTID | hkg_br_base_segment_used_by_dependent_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| br_campaign_segment.SEGMENTID | hkg_br_collection_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| br_campaign_segment.SEGMENTID | hkg_br_segment_property.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| br_campaign_segment.SEGMENTID | hkg_br_segment_target.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| dim_blueprint.BLUEPRINTID | hkg_br_blueprint_collection.BLUEPRINTID | schema-level relationship | Matching ID-like column name. |
| dim_blueprint.BLUEPRINTID | hkg_br_blueprint_property.BLUEPRINTID | schema-level relationship | Matching ID-like column name. |
| dim_collection.COLLECTIONID | hkg_br_blueprint_collection.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| dim_collection.COLLECTIONID | hkg_br_collection_property.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| dim_collection.COLLECTIONID | hkg_br_collection_segment.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| dim_collection.COLLECTIONID | hkg_br_source_collection.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| dim_connector.SOURCEID | hkg_br_source_collection.SOURCEID | schema-level relationship | Matching ID-like column name. |
| dim_segment.SEGMENTID | hkg_br_base_segment_used_by_dependent_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| dim_segment.SEGMENTID | hkg_br_collection_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| dim_segment.SEGMENTID | hkg_br_segment_property.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| dim_target.TARGETID | hkg_br_target_property.TARGETID | schema-level relationship | Matching ID-like column name. |
| hkg_br_base_segment_used_by_dependent_segment.SEGMENTID | hkg_br_collection_segment.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_base_segment_used_by_dependent_segment.SEGMENTID | hkg_br_segment_property.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_base_segment_used_by_dependent_segment.SEGMENTID | hkg_br_segment_target.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_blueprint_collection.COLLECTIONID | hkg_br_collection_property.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_blueprint_collection.COLLECTIONID | hkg_br_collection_segment.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_blueprint_collection.COLLECTIONID | hkg_br_source_collection.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_blueprint_property.BLUEPRINTID | hkg_br_blueprint_collection.BLUEPRINTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_collection_property.COLLECTIONID | hkg_br_collection_segment.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_collection_property.COLLECTIONID | hkg_br_source_collection.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_collection_segment.SEGMENTID | hkg_br_segment_property.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_collection_segment.SEGMENTID | hkg_br_segment_target.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_segment_property.SEGMENTID | hkg_br_segment_target.SEGMENTID | schema-level relationship | Matching ID-like column name. |
| hkg_br_source_collection.COLLECTIONID | hkg_br_collection_segment.COLLECTIONID | schema-level relationship | Matching ID-like column name. |
| hkg_br_target_property.TARGETID | hkg_br_segment_target.TARGETID | schema-level relationship | Matching ID-like column name. |
| dim_segment.SEGMENTID | hkg_br_base_segment_used_by_dependent_segment.DEPENDENTSEGMENTID | naming convention | Foreign-key-looking column references table root. |

## Per Example

| Query ID | Tables | APIs | Confidence | Context mode | Used gold patterns |
| --- | --- | --- | ---: | --- | --- |
| `example_000` | dim_campaign, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment, hkg_br_collection_segment, hkg_br_segment_property | journey_list, schema_registry_schema, unified_tag_detail, audit_events, audit_events_short | 0.92 | candidate | False |
| `example_001` | dim_campaign, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment, hkg_br_segment_property | journey_list, audit_events, audit_events_short, catalog_batch_detail, catalog_batches | 0.74 | expanded_candidate | False |
| `example_002` | dim_campaign, br_campaign_segment, dim_blueprint, dim_collection, dim_connector | journey_list, catalog_batches, catalog_datasets, export_batch_failed, export_batch_files | 0.92 | candidate | False |
| `example_003` | dim_segment, dim_collection, dim_target, hkg_br_segment_target, hkg_br_base_segment_used_by_dependent_segment | ups_audiences, segment_definitions, audit_events, audit_events_short, segment_jobs | 1.0 | candidate | False |
| `example_004` | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | flowservice_runs, flowservice_flows, export_batch_failed, audit_events, audit_events_short | 0.72 | hybrid | False |
| `example_005` | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_blueprint_collection | export_batch_files, export_batch_failed, flowservice_flows, audit_events, catalog_datasets | 0.6 | hybrid | False |
| `example_006` | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection, dim_campaign | catalog_datasets, export_batch_files, schema_registry_schema, schema_registry_schemas, audit_events | 0.9246 | candidate | False |
| `example_007` | dim_blueprint, dim_segment, br_campaign_segment, dim_collection, hkg_br_blueprint_property | schema_registry_schema, schema_registry_schemas, catalog_datasets, schemas_short, catalog_batches | 0.8635 | candidate | False |
| `example_008` | hkg_br_segment_property, dim_collection, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment | audit_events, audit_events_short, export_batch_failed, export_batch_files, schema_registry_schema | 0.8187 | candidate | False |
| `example_009` | dim_blueprint, hkg_br_blueprint_collection, dim_collection, hkg_br_blueprint_property, hkg_br_collection_property | schemas_short, schema_registry_schemas, schema_registry_schema, audit_events, audit_events_short | 0.8438 | candidate | False |
| `example_010` | dim_blueprint, dim_collection, dim_segment, br_campaign_segment, hkg_br_blueprint_property | schemas_short, schema_registry_schemas, audit_events, audit_events_short, catalog_batches | 0.5164 | hybrid | False |
| `example_011` | hkg_br_blueprint_collection, dim_blueprint, dim_collection, br_campaign_segment, hkg_br_collection_segment | schema_registry_schemas, schemas_short, schema_registry_schema, audit_events, audit_events_short | 0.9831 | candidate | False |
| `example_012` | dim_target, hkg_br_blueprint_collection, hkg_br_blueprint_property, dim_connector, dim_blueprint | ups_audiences, segment_definitions, export_batch_files, flowservice_flows, merge_policies | 0.758 | candidate | False |
| `example_013` | hkg_br_blueprint_collection, dim_blueprint, hkg_br_blueprint_property, dim_collection, dim_segment | catalog_datasets, audit_events, export_batch_files, audit_events_short, catalog_batch_detail | 0.9387 | candidate | False |
| `example_014` | hkg_br_base_segment_used_by_dependent_segment, hkg_br_segment_target, dim_collection, dim_segment, dim_target | audit_events, audit_events_short, catalog_batch_detail, export_batch_files, catalog_batches | 0.8284 | candidate | False |
| `example_015` | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment, hkg_br_blueprint_collection | unified_tags, unified_tag_categories, unified_tag_detail, export_batch_files, audit_events | 0.7387 | expanded_candidate | False |
| `example_016` | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment, hkg_br_blueprint_collection | unified_tags, unified_tag_categories, export_batch_files, journey_list, unified_tag_detail | 0.7387 | expanded_candidate | False |
| `example_017` | dim_connector, dim_blueprint, dim_collection, br_campaign_segment, hkg_br_blueprint_property | unified_tag_categories, unified_tags, unified_tag_detail, audit_events, audit_events_short | 0.6875 | expanded_candidate | False |
| `example_018` | br_campaign_segment, hkg_br_collection_segment, hkg_br_segment_property, hkg_br_segment_target, dim_blueprint | unified_tag_categories, unified_tags, unified_tag_detail, catalog_batch_detail, schema_registry_schema | 0.6471 | hybrid | False |
| `example_019` | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment, hkg_br_blueprint_collection | merge_policies, export_batch_files, journey_list, catalog_batches, catalog_datasets | 0.7387 | expanded_candidate | False |
| `example_020` | hkg_br_blueprint_property, dim_blueprint, dim_campaign, dim_segment, hkg_br_blueprint_collection | merge_policies, export_batch_files, audit_events, audit_events_short, catalog_batch_detail | 0.7387 | expanded_candidate | False |
| `example_021` | dim_blueprint, dim_segment, br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property | merge_policies, audit_events, audit_events_short, export_batch_failed, export_batch_files | 0.7067 | expanded_candidate | False |
| `example_022` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_definitions, ups_audiences, segment_jobs, export_batch_files, merge_policies | 1.0 | candidate | False |
| `example_023` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_definitions, ups_audiences, segment_jobs, merge_policies, journey_list | 1.0 | candidate | False |
| `example_024` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_definitions, ups_audiences, segment_jobs, merge_policies, audit_events | 1.0 | candidate | False |
| `example_025` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_jobs, merge_policies, ups_audiences, journey_list, segment_definitions | 1.0 | candidate | False |
| `example_026` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_jobs, segment_definitions, merge_policies, ups_audiences, audit_events | 1.0 | candidate | False |
| `example_027` | hkg_br_segment_target, dim_segment, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, hkg_br_collection_segment | segment_jobs, segment_definitions, audit_events, audit_events_short, catalog_batches | 1.0 | candidate | False |
| `example_028` | dim_collection, dim_segment, hkg_br_segment_target, dim_blueprint, dim_target | catalog_batches, audit_events, audit_events_short, export_batch_failed, export_batch_files | 0.6848 | expanded_candidate | False |
| `example_029` | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property | catalog_batches, export_batch_failed, catalog_batch_detail, export_batch_files, audit_events | 0.6956 | expanded_candidate | False |
| `example_030` | br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property, hkg_br_collection_segment, hkg_br_segment_property | catalog_batch_detail, export_batch_failed, export_batch_files, schema_registry_schema, unified_tag_detail | 0.2636 | hybrid | False |
| `example_031` | dim_segment, hkg_br_blueprint_collection, dim_collection, dim_blueprint, hkg_br_blueprint_property | export_batch_files, audit_events, audit_events_short, export_batch_failed, catalog_batch_detail | 0.758 | candidate | False |
| `example_032` | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property | export_batch_failed, export_batch_files, catalog_batch_detail, audit_events, audit_events_short | 0.47 | expanded_candidate | False |
| `example_033` | dim_campaign, br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property, hkg_br_collection_segment | observability_metrics, catalog_batches, catalog_datasets, audit_events, audit_events_short | 0.548 | expanded_candidate | False |
| `example_034` | dim_campaign, dim_segment, br_campaign_segment, hkg_br_blueprint_property, hkg_br_collection_property | ups_audiences, audit_events, audit_events_short, catalog_datasets, export_batch_failed | 0.33 | hybrid | False |

## Robust Schema Linking Metrics

| Query ID | Forward links | Backward links | Structural join preserved | Link confidence | Risk | Context reason |
| --- | ---: | ---: | --- | ---: | --- | --- |
| `example_000` | 6 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_001` | 66 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_002` | 1 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_003` | 88 | 21 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_004` | 72 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_005` | 150 | 0 | True | 0.98 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_006` | 25 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_007` | 3 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_008` | 61 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_009` | 1 | 0 | True | 0.9788 | low | strong bidirectional links; structural bridge preserved |
| `example_010` | 14 | 1 | True | 0.8964 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_011` | 113 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_012` | 32 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_013` | 22 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_014` | 79 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_015` | 27 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_016` | 27 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_017` | 9 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_018` | 65 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_019` | 26 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_020` | 27 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_021` | 8 | 2 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_022` | 50 | 2 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_023` | 26 | 2 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_024` | 36 | 2 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_025` | 24 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_026` | 25 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_027` | 36 | 2 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_028` | 12 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_029` | 8 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_030` | 3 | 0 | True | 0.4686 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_031` | 26 | 0 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_032` | 8 | 0 | True | 0.85 | low | strong bidirectional links; structural bridge preserved |
| `example_033` | 8 | 0 | True | 0.928 | low | strong bidirectional links; structural bridge preserved |
| `example_034` | 7 | 0 | True | 0.675 | medium | weak schema links or small score margin; structural bridge preserved |

## Hybrid Ranking Diagnostics

| Query ID | Ranking changed? | Top table score | Table margin | Endpoint family | Endpoint confidence | Endpoint ranking changed? |
| --- | --- | ---: | ---: | --- | ---: | --- |
| `example_000` | True | 1.8 | 1.3 | journey_list | 1.0 | False |
| `example_001` | True | 1.8 | 0.1 | journey_list | 1.0 | False |
| `example_002` | True | 1.8 | 1.3 | journey_list | 1.0 | False |
| `example_003` | True | 2.965 | 0.165 | segment_definitions | 1.0 | True |
| `example_004` | True | 1.8 | 0.0 | flow_runs | 1.0 | True |
| `example_005` | True | 1.8 | 0.0 | None | 0.0 | True |
| `example_006` | True | 2.21 | 0.41 | dataset_list | 0.8825 | True |
| `example_007` | True | 1.7 | 0.92 | schema_detail | 0.94 | True |
| `example_008` | True | 2.21 | 0.41 | None | 0.0 | False |
| `example_009` | True | 1.8 | 0.7 | schema_list | 0.865 | True |
| `example_010` | True | 1.2 | 0.0 | schema_list | 0.97 | True |
| `example_011` | True | 2.3 | 0.5 | schema_list | 0.97 | True |
| `example_012` | True | 1.8 | 0.19 | segment_definitions | 1.0 | True |
| `example_013` | True | 2.21 | 0.41 | dataset_list | 1.0 | True |
| `example_014` | True | 2.215 | 0.005 | audit_events | 0.7425 | False |
| `example_015` | True | 1.61 | 0.41 | tag_list | 1.0 | True |
| `example_016` | True | 1.61 | 0.41 | tag_list | 1.0 | True |
| `example_017` | True | 1.46 | 0.47 | tag_list | 0.89 | True |
| `example_018` | True | 1.61 | 0.0 | tag_list | 0.92 | True |
| `example_019` | True | 1.61 | 0.41 | merge_policies | 1.0 | True |
| `example_020` | True | 1.61 | 0.41 | merge_policies | 1.0 | False |
| `example_021` | True | 1.55 | 0.35 | merge_policies | 1.0 | True |
| `example_022` | True | 2.725 | 0.06 | segment_definitions | 1.0 | True |
| `example_023` | True | 2.725 | 0.06 | segment_definitions | 1.0 | True |
| `example_024` | True | 2.725 | 0.06 | segment_definitions | 1.0 | True |
| `example_025` | True | 2.725 | 0.41 | segment_jobs | 0.9725 | True |
| `example_026` | True | 2.725 | 0.41 | segment_jobs | 0.9725 | True |
| `example_027` | True | 2.725 | 0.41 | segment_jobs | 0.9725 | True |
| `example_028` | True | 1.59 | 0.33 | batch_list | 0.74 | True |
| `example_029` | True | 1.55 | 0.41 | batch_list | 0.8075 | True |
| `example_030` | True | 0.5 | 0.0 | batch_details | 0.8075 | False |
| `example_031` | True | 1.8 | 0.19 | batch_files | 1.0 | True |
| `example_032` | True | 0.96 | 0.15 | batch_failed_files | 1.0 | True |
| `example_033` | True | 0.99 | 0.49 | observability_metrics | 1.0 | False |
| `example_034` | True | 0.99 | 0.0 | None | 0.0 | False |
