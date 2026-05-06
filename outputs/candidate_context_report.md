# Candidate Context Report

Candidate context is schema/API retrieval only. It does not use public gold patterns or decide final SQL.

## Summary

| Metric | Value |
| --- | ---: |
| avg_candidate_context_tokens | 2261.6 |
| avg_full_schema_context_tokens | 4682 |
| compression_ratio | 0.483 |
| table_recall_at_3 | 0.7667 |
| table_recall_at_5 | 0.8667 |
| api_recall_at_3 | 0.4677 |
| api_recall_at_5 | 0.5484 |
| candidate_low_confidence_count | 14 |
| candidate_zero_margin_count | 32 |
| percent_low_confidence | 0.4 |
| percent_zero_margin | 0.9143 |
| recommended_fallback_rate | 0.9143 |
| context_mode_distribution | {'candidate': 3, 'hybrid': 32} |
| avg_forward_link_count | 34.0286 |
| avg_backward_link_count | 1.2 |
| structural_join_preserved_count | 35 |
| schema_link_risk_distribution | {'low': 3, 'medium': 29, 'high': 3} |

## Candidate Miss Analysis

| Query ID | Missing tables | Missing APIs | Confidence | Margin | Recommended mode |
| --- | --- | --- | ---: | ---: | --- |
| `example_003` |  | /data/foundation/flowservice/flows | 0.85 | 0.0 | hybrid |
| `example_004` |  |  | 0.6667 | 0.0 | hybrid |
| `example_005` |  |  | 0.6667 | 0.0 | hybrid |
| `example_006` |  | /data/foundation/catalog/dataSets, /data/foundation/schemaregistry/tenant/schemas/{schema_id} | 0.6667 | 0.0 | hybrid |
| `example_007` | dim_blueprint, dim_collection | /data/foundation/schemaregistry/tenant/schemas/{schema_id} | 0.0833 | 0.0 | hybrid |
| `example_008` |  |  | 0.6667 | 0.0 | hybrid |
| `example_009` |  |  | 0.6667 | 0.0 | hybrid |
| `example_010` | dim_blueprint | /data/foundation/schemaregistry/tenant/schemas | 0.0833 | 0.0 | hybrid |
| `example_011` |  | /schemas | 0.6667 | 0.0 | hybrid |
| `example_012` |  | /data/foundation/audit/events | 0.6667 | 0.0 | hybrid |
| `example_013` |  |  | 0.6667 | 0.0 | hybrid |
| `example_014` |  |  | 0.6667 | 0.0 | hybrid |
| `example_015` |  | /unifiedtags/tags | 0.0833 | 0.0 | hybrid |
| `example_016` |  | /unifiedtags/tags | 0.0833 | 0.0 | hybrid |
| `example_017` |  | /unifiedtags/tags | 0.0833 | 0.0 | hybrid |
| `example_018` |  | /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818 | 0.0833 | 0.0 | hybrid |
| `example_019` |  |  | 0.0833 | 0.0 | hybrid |
| `example_020` |  |  | 0.0833 | 0.0 | hybrid |
| `example_021` |  |  | 0.0833 | 0.0 | hybrid |
| `example_022` |  |  | 0.85 | 0.0 | hybrid |
| `example_023` |  |  | 0.85 | 0.0 | hybrid |
| `example_024` |  |  | 0.85 | 0.0 | hybrid |
| `example_025` |  |  | 0.85 | 0.0 | hybrid |
| `example_026` |  |  | 0.85 | 0.0 | hybrid |
| `example_027` |  |  | 0.85 | 0.0 | hybrid |
| `example_028` |  | /data/foundation/catalog/batches | 0.6667 | 0.0 | hybrid |
| `example_029` |  |  | 0.0833 | 0.0 | hybrid |
| `example_030` |  | /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F | 0.0833 | 0.0 | hybrid |
| `example_031` |  | /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 0.6667 | 0.0 | hybrid |
| `example_032` |  | /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed | 0.0833 | 0.0 | hybrid |
| `example_033` |  |  | 0.0833 | 0.0 | hybrid |
| `example_034` |  | /data/infrastructure/observability/insights/metrics | 0.0833 | 0.0 | hybrid |

## Candidate Risk Clusters

These clusters are diagnostic-only and do not change candidate ranking, SQL generation, or answer behavior.

| Cluster | Count | Example query IDs | Diagnostic only | Behavior changing? | Likely safe improvement |
| --- | ---: | --- | --- | --- | --- |
| `zero_score_margin` | 32 | example_003, example_004, example_005, example_006, example_007, example_008, example_009, example_010 | True | False | Improve tie-break diagnostics or fall back to hybrid/full schema context; do not force a table choice from a tied score. |
| `low_confidence` | 14 | example_007, example_010, example_015, example_016, example_017, example_018, example_019, example_020 | True | False | Use broader context and surface the uncertainty to LLM/controller paths instead of narrowing aggressively. |
| `missing_gold_table_in_top_k` | 2 | example_007, example_010 | True | False | Audit schema aliases and structural bridge coverage using schema-level signals only. |
| `missing_gold_api_in_top_k` | 15 | example_003, example_006, example_007, example_010, example_011, example_012, example_015, example_016 | True | False | Improve endpoint catalog descriptions and API-family aliases without using public answer patterns. |
| `broad_domain_api_confusion` | 11 | example_005, example_006, example_012, example_015, example_016, example_019, example_020, example_022 | True | False | Add endpoint-family labels and confidence diagnostics for broad platform/API intents. |
| `schema_vs_dataset_confusion` | 8 | example_006, example_007, example_009, example_010, example_011, example_013, example_021, example_033 | True | False | Clarify schema-vs-dataset table/API affordances in retrieval-only metadata. |
| `tag_api_confusion` | 4 | example_015, example_016, example_017, example_018 | True | False | Strengthen tag endpoint summaries and keep dry-run API evidence labeled separately. |
| `batch_endpoint_confusion` | 11 | example_003, example_007, example_010, example_014, example_021, example_028, example_029, example_030 | True | False | Audit batch endpoint family labels and alias repair diagnostics. |

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
| `example_000` | dim_campaign, dim_connector, dim_segment, dim_target, br_campaign_segment | journey_list, schema_registry_schema, unified_tag_detail | 0.8667 | candidate | False |
| `example_001` | dim_campaign, dim_connector, dim_segment, dim_target, br_campaign_segment | journey_list | 0.8667 | candidate | False |
| `example_002` | dim_campaign, br_campaign_segment | journey_list, catalog_batches, catalog_datasets, export_batch_failed, export_batch_files | 0.8667 | candidate | False |
| `example_003` | dim_segment, hkg_br_segment_target, dim_collection, dim_target, hkg_br_base_segment_used_by_dependent_segment | audit_events, audit_events_short, merge_policies, segment_jobs, ups_audiences | 0.85 | hybrid | False |
| `example_004` | dim_connector, dim_target, hkg_br_source_collection, dim_campaign, dim_segment | flowservice_runs, audit_events, export_batch_failed, flowservice_flows | 0.6667 | hybrid | False |
| `example_005` | dim_connector, dim_target, hkg_br_base_segment_used_by_dependent_segment, br_campaign_segment, dim_blueprint | export_batch_files, export_batch_failed, flowservice_flows, audit_events, catalog_datasets | 0.6667 | hybrid | False |
| `example_006` | dim_blueprint, dim_collection, hkg_br_blueprint_collection, dim_campaign, dim_connector | export_batch_files, audit_events, audit_events_short, catalog_batch_detail, catalog_batches | 0.6667 | hybrid | False |
| `example_007` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | catalog_batches, catalog_datasets, export_batch_failed, export_batch_files, schema_registry_schemas | 0.0833 | hybrid | False |
| `example_008` | dim_collection, dim_segment, hkg_br_collection_property, hkg_br_segment_property, dim_blueprint | audit_events, audit_events_short, export_batch_failed, export_batch_files, schema_registry_schema | 0.6667 | hybrid | False |
| `example_009` | dim_blueprint, dim_collection, hkg_br_blueprint_collection, hkg_br_blueprint_property, hkg_br_collection_property | audit_events, audit_events_short, catalog_batch_detail, export_batch_failed, export_batch_files | 0.6667 | hybrid | False |
| `example_010` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | audit_events, audit_events_short, catalog_batches, export_batch_failed, export_batch_files | 0.0833 | hybrid | False |
| `example_011` | dim_blueprint, dim_collection, hkg_br_blueprint_collection, br_campaign_segment, dim_campaign | audit_events, audit_events_short, catalog_batch_detail, catalog_batches, catalog_datasets | 0.6667 | hybrid | False |
| `example_012` | dim_connector, dim_target, dim_segment, dim_blueprint, dim_campaign | export_batch_files, flowservice_flows, merge_policies, segment_jobs, ups_audiences | 0.6667 | hybrid | False |
| `example_013` | dim_blueprint, dim_collection, hkg_br_blueprint_collection, dim_campaign, dim_connector | audit_events, export_batch_files, audit_events_short, catalog_batch_detail, catalog_batches | 0.6667 | hybrid | False |
| `example_014` | dim_collection, dim_segment, dim_target, hkg_br_segment_target, hkg_br_base_segment_used_by_dependent_segment | audit_events, audit_events_short, catalog_batch_detail, export_batch_files | 0.6667 | hybrid | False |
| `example_015` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | unified_tag_categories, export_batch_files, unified_tag_detail | 0.0833 | hybrid | False |
| `example_016` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | unified_tag_categories, export_batch_files, catalog_batches, catalog_datasets, export_batch_failed | 0.0833 | hybrid | False |
| `example_017` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | unified_tag_categories, unified_tag_detail | 0.0833 | hybrid | False |
| `example_018` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | unified_tag_categories, unified_tag_detail, catalog_batch_detail, schema_registry_schema | 0.0833 | hybrid | False |
| `example_019` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | merge_policies, export_batch_files, catalog_batches, catalog_datasets, export_batch_failed | 0.0833 | hybrid | False |
| `example_020` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | merge_policies, export_batch_files | 0.0833 | hybrid | False |
| `example_021` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | audit_events, audit_events_short, export_batch_failed, export_batch_files, merge_policies | 0.0833 | hybrid | False |
| `example_022` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_definitions, export_batch_files, merge_policies, segment_jobs, ups_audiences | 0.85 | hybrid | False |
| `example_023` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_definitions, merge_policies, segment_jobs, ups_audiences, catalog_batches | 0.85 | hybrid | False |
| `example_024` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_definitions, merge_policies, segment_jobs, ups_audiences | 0.85 | hybrid | False |
| `example_025` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_jobs, merge_policies, ups_audiences, catalog_batches, catalog_datasets | 0.85 | hybrid | False |
| `example_026` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_jobs, merge_policies, segment_definitions, ups_audiences | 0.85 | hybrid | False |
| `example_027` | dim_segment, hkg_br_segment_target, dim_target, br_campaign_segment, hkg_br_base_segment_used_by_dependent_segment | segment_jobs, audit_events, audit_events_short, catalog_batches, export_batch_failed | 0.85 | hybrid | False |
| `example_028` | dim_collection, dim_segment, dim_target, hkg_br_segment_target, dim_blueprint | audit_events, audit_events_short, export_batch_failed, export_batch_files, catalog_batch_detail | 0.6667 | hybrid | False |
| `example_029` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | export_batch_failed, audit_events, audit_events_short, catalog_batch_detail, catalog_batches | 0.0833 | hybrid | False |
| `example_030` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | catalog_batch_detail, export_batch_failed, export_batch_files, schema_registry_schema, unified_tag_detail | 0.0833 | hybrid | False |
| `example_031` | dim_collection, dim_segment, dim_target, hkg_br_segment_target, dim_property | audit_events, audit_events_short, export_batch_files, export_batch_failed, catalog_batch_detail | 0.6667 | hybrid | False |
| `example_032` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | export_batch_failed, export_batch_files, audit_events, audit_events_short, catalog_batch_detail | 0.0833 | hybrid | False |
| `example_033` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | observability_metrics, catalog_batches, catalog_datasets, audit_events, audit_events_short | 0.0833 | hybrid | False |
| `example_034` | br_campaign_segment, dim_property, dim_target, hkg_br_base_segment_used_by_dependent_segment, hkg_br_blueprint_collection | ups_audiences, audit_events, audit_events_short, catalog_datasets, export_batch_failed | 0.0833 | hybrid | False |

## Robust Schema Linking Metrics

| Query ID | Forward links | Backward links | Structural join preserved | Link confidence | Risk | Context reason |
| --- | ---: | ---: | --- | ---: | --- | --- |
| `example_000` | 6 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_001` | 66 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_002` | 1 | 1 | True | 1.0 | low | strong bidirectional links; structural bridge preserved |
| `example_003` | 88 | 21 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_004` | 72 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_005` | 150 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_006` | 25 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_007` | 3 | 1 | True | 0.3233 | high | weak schema links or small score margin; structural bridge preserved |
| `example_008` | 61 | 1 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_009` | 1 | 0 | True | 0.8017 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_010` | 14 | 1 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_011` | 113 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_012` | 32 | 1 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_013` | 22 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_014` | 79 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_015` | 27 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_016` | 27 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_017` | 9 | 1 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_018` | 65 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_019` | 26 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_020` | 27 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_021` | 8 | 2 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_022` | 50 | 2 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_023` | 26 | 2 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_024` | 36 | 2 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_025` | 24 | 1 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_026` | 25 | 1 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_027` | 36 | 2 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_028` | 12 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_029` | 8 | 1 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_030` | 3 | 0 | True | 0.2883 | high | weak schema links or small score margin; structural bridge preserved |
| `example_031` | 26 | 0 | True | 1.0 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_032` | 8 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_033` | 8 | 0 | True | 0.4633 | medium | weak schema links or small score margin; structural bridge preserved |
| `example_034` | 7 | 0 | True | 0.4283 | high | weak schema links or small score margin; structural bridge preserved |
