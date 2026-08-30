# Endpoint/Schema Rule Candidate Eval

This is a shadow-only rule candidate report. No packaged execution behavior changed.

- Candidate rules: 18
- Safe for future canary rules: 18
- Affected query count: 28
- Total top-k API hit delta: 2
- Hidden-style gate passed: True

| Rule | Target | Affected | Top-k hit delta | Leakage OK? | Future canary? |
| --- | --- | ---: | ---: | --- | --- |
| `batch_id_file_family` | batch_endpoint_confusion | 0 | 0 | True | True |
| `failed_batch_file_family` | batch_endpoint_confusion | 0 | 0 | True | True |
| `tag_category_detail_list_family` | tag_api_confusion | 3 | 0 | True | True |
| `tag_named_detail_family` | zero_score_margin | 1 | 0 | True | True |
| `schema_dataset_relation_family` | schema_vs_dataset_confusion | 2 | 0 | True | True |
| `schema_named_detail_family` | broad_domain_api_confusion | 1 | 0 | True | True |
| `journey_status_date_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `destination_flow_listing_family` | zero_score_margin | 1 | 0 | True | True |
| `audience_destination_mapping_family` | missing_api_candidate | 2 | 1 | True | True |
| `dataflow_run_status_family` | zero_score_margin | 1 | 0 | True | True |
| `segment_job_status_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `merge_policy_default_class_family` | broad_domain_api_confusion | 3 | 0 | True | True |
| `dataset_audit_change_family` | broad_domain_api_confusion | 1 | 0 | True | True |
| `audit_entity_creator_family` | broad_domain_api_confusion | 1 | 0 | True | True |
| `observability_timeseries_metric_family` | broad_domain_api_confusion | 1 | 0 | True | True |
| `observability_ingestion_metric_family` | zero_score_margin | 1 | 1 | True | True |
| `zero_margin_endpoint_family_tiebreak` | zero_score_margin | 6 | 0 | True | True |
| `missing_api_topk_family_coverage` | missing_api_candidate | 7 | 0 | True | True |

## Leakage Guard

- Runtime triggers use reusable vocabulary, schema relation wording, endpoint catalog metadata, and path-shape signals.
- No rule uses query_id, exact public query strings, gold SQL/API paths, or memorized answers.
- Declared dependency: `codex/score075-robustness-leakage`.

## Worker 4 Summary

- Branch: `codex/score075-endpoint-routing`
- Baseline commit: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Declared dependency: `codex/score075-robustness-leakage`
- Merge recommendation: `candidate_only_for_integration_review`
- Packaged execution changed: false
- Scorer changed: false
- Final submission touched: false
- Repair execution enabled: false
- Compact context enabled: false

## Blockers

- Depends on robustness/leakage worker before integration merge.
