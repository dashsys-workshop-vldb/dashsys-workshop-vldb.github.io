# Hidden-Style Generalization Eval

- Total cases: 48
- Passed cases: 47
- Failed cases: 1
- Family-stability rate: 1.0
- Schema-stability rate: 0.9792
- Top failure categories: [('schema_family_missing', 1)]

| Case | Family | Top API | Family stable? | Schema stable? | Passed? | Failures |
| --- | --- | --- | --- | --- | --- | --- |
| `batch_files_a` | batch_files | export_batch_files | True | True | True |  |
| `batch_files_b` | batch_files | export_batch_files | True | True | True |  |
| `batch_files_c` | batch_files | export_batch_files | True | True | True |  |
| `batch_failed_a` | batch_failed_files | export_batch_failed | True | True | True |  |
| `batch_failed_b` | batch_failed_files | export_batch_failed | True | True | True |  |
| `batch_failed_c` | batch_failed_files | export_batch_failed | True | True | True |  |
| `batch_detail_a` | batch_details | catalog_batch_detail | True | True | True |  |
| `batch_count_a` | batch_list | catalog_batches | True | True | True |  |
| `tag_count_a` | tag_list | unified_tags | True | True | True |  |
| `tag_count_b` | tag_list | unified_tags | True | True | True |  |
| `tag_list_a` | tag_list | unified_tags | True | True | True |  |
| `tag_detail_a` | tag_list | unified_tags | True | True | True |  |
| `tag_detail_b` | tag_list | unified_tags | True | True | True |  |
| `tag_category_a` | tag_list | unified_tags | True | True | True |  |
| `tag_category_b` | tag_list | unified_tags | True | True | True |  |
| `schema_list_a` | schema_list | schema_registry_schemas | True | True | True |  |
| `schema_count_a` | schema_list | schema_registry_schemas | True | True | True |  |
| `schema_detail_a` | schema_list | schema_registry_schemas | True | True | True |  |
| `schema_detail_b` | schema_list | schema_registry_schemas | True | True | True |  |
| `schema_dataset_a` | schema_detail | schema_registry_schema | True | True | True |  |
| `schema_dataset_b` | dataset_list | catalog_datasets | True | False | False | schema_family_missing |
| `schema_dataset_c` | dataset_list | catalog_datasets | True | True | True |  |
| `journey_status_a` | journey_list | journey_list | True | True | True |  |
| `journey_status_b` | journey_list | journey_list | True | True | True |  |
| `journey_date_a` | journey_list | journey_list | True | True | True |  |
| `journey_date_b` | journey_list | journey_list | True | True | True |  |
| `journey_list_a` | journey_list | journey_list | True | True | True |  |
| `journey_list_b` | journey_list | journey_list | True | True | True |  |
| `segment_jobs_a` | segment_jobs | segment_jobs | True | True | True |  |
| `segment_jobs_b` | segment_jobs | segment_jobs | True | True | True |  |
| `segment_jobs_c` | segment_jobs | segment_jobs | True | True | True |  |
| `segment_defs_a` | segment_definitions | segment_definitions | True | True | True |  |
| `segment_defs_b` | segment_definitions | segment_definitions | True | True | True |  |
| `segment_defs_c` | segment_definitions | segment_definitions | True | True | True |  |
| `merge_policies_a` | merge_policies | merge_policies | True | True | True |  |
| `merge_policies_b` | merge_policies | merge_policies | True | True | True |  |
| `merge_policies_c` | merge_policies | merge_policies | True | True | True |  |
| `audit_events_a` | audit_events | audit_events | True | True | True |  |
| `audit_events_b` | audit_events | audit_events | True | True | True |  |
| `audit_events_c` | audit_events | audit_events | True | True | True |  |
| `observability_metrics_a` | observability_metrics | observability_metrics | True | True | True |  |
| `observability_metrics_b` | observability_metrics | observability_metrics | True | True | True |  |
| `observability_metrics_c` | observability_metrics | observability_metrics | True | True | True |  |
| `flow_runs_a` | flow_runs | flowservice_runs | True | True | True |  |
| `flow_defs_a` | flow_definitions | flowservice_flows | True | True | True |  |
| `broad_sandbox_a` | None | audit_events | True | True | True |  |
| `broad_sandbox_b` | None | audit_events | True | True | True |  |
| `broad_sandbox_c` | None | audit_events | True | True | True |  |
