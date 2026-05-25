# Guarded Dash Agent Live E2E Trial

Diagnostic-only live Adobe trial over supported GET endpoint families. No mutating calls were executed.

- Status: `pass`
- Trial queries: `12`
- Live API calls attempted: `12`
- Live success: `9`
- Live empty: `3`
- API failures: `0`
- Parser successes: `12`
- Usable live API evidence: `9`
- API state forwarded: `12`
- Answers used usable API evidence: `9`
- Unsupported API claims: `0`
- Parser/EvidenceBus failures: `0`
- Unresolved path failures: `0`

## Trial Rows

- `audience_list` route=`audience_segment` endpoint=`ups_audiences` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `segment_definition_list` route=`audience_segment` endpoint=`segment_definitions` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `merge_policy_list` route=`merge_policies` endpoint=`merge_policies` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `destination_flows` route=`flows_runs` endpoint=`flowservice_flows` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `flow_runs` route=`flows_runs` endpoint=`flowservice_runs` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `dataset_list` route=`datasets_batches` endpoint=`catalog_datasets` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `batch_list` route=`datasets_batches` endpoint=`catalog_batches` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `tenant_schema_list` route=`schemas` endpoint=`schema_registry_schemas` outcome=`live_empty` parser=`pass` usable_evidence=`False` answer_usage=`used_api_state_caveat`
- `schema_short_alias` route=`schemas` endpoint=`schemas_short` outcome=`live_empty` parser=`pass` usable_evidence=`False` answer_usage=`used_api_state_caveat`
- `audit_events` route=`audit_events` endpoint=`audit_events_short` outcome=`live_empty` parser=`pass` usable_evidence=`False` answer_usage=`used_api_state_caveat`
- `unified_tags` route=`tags` endpoint=`unified_tags` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
- `unified_tag_categories` route=`tags` endpoint=`unified_tag_categories` outcome=`live_success` parser=`pass` usable_evidence=`True` answer_usage=`used_usable_api_evidence`
