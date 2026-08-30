# Endpoint/Schema Rule Candidate Eval

This is a shadow-only rule candidate report. No packaged execution behavior changed.

- Candidate rules: 10
- Safe for future canary rules: 9
- Affected query count: 25
- Total top-k API hit delta: 0
- Hidden-style gate passed: True

| Rule | Target | Affected | Top-k hit delta | Leakage OK? | Future canary? |
| --- | --- | ---: | ---: | --- | --- |
| `batch_id_file_family` | batch_endpoint_confusion | 0 | 0 | True | True |
| `failed_batch_file_family` | batch_endpoint_confusion | 0 | 0 | True | True |
| `tag_category_detail_list_family` | tag_api_confusion | 3 | 0 | True | True |
| `schema_dataset_relation_family` | schema_vs_dataset_confusion | 2 | 0 | True | True |
| `journey_status_date_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `segment_job_status_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `merge_policy_default_class_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `observability_timeseries_metric_family` | broad_domain_api_confusion | 1 | 0 | True | True |
| `zero_margin_endpoint_family_tiebreak` | zero_score_margin | 6 | 0 | True | True |
| `missing_api_topk_family_coverage` | missing_gold_api_in_top_k | 4 | 0 | False | False |
