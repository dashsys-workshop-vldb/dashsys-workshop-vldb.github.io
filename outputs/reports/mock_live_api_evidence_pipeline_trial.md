# Mock Live API Evidence Pipeline Trial

Infrastructure validation only; this report does not compute or claim official strict-score improvement.

- Status: `complete`
- Mocked live cases: `126`
- Endpoint families covered: `21`
- Parser success count: `126`
- EvidenceBus forwarding count: `105`
- Answer slot success count: `126`
- Answer used API evidence count: `126`
- Unsupported API claim count: `0`
- Empty live result handling count: `21`
- API error handling count: `21`
- Malformed response handling count: `21`
- Discovery-chain simulated count: `5`
- Recommendation: `mock_live_pipeline_ready_for_future_credentialed_smoke`

## Endpoint Families Covered

- `audit_events`
- `audit_events_short`
- `catalog_batch_detail`
- `catalog_batches`
- `catalog_datasets`
- `export_batch_failed`
- `export_batch_files`
- `flowservice_flows`
- `flowservice_runs`
- `journey_list`
- `merge_policies`
- `observability_metrics`
- `schema_registry_schema`
- `schema_registry_schemas`
- `schemas_short`
- `segment_definitions`
- `segment_jobs`
- `unified_tag_categories`
- `unified_tag_detail`
- `unified_tags`
- `ups_audiences`

## Example Evidence Usage

- `journey_list_normal` source=`live_api` answer=Based on live API evidence, the matching item(s) are: Welcome Journey.
- `journey_list_empty` source=`live_api` answer=The requested journey list list requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.
- `journey_list_error` source=`api_error` answer=The requested journey list list requires live API evidence. API evidence did not provide usable data.
- `journey_list_pagination` source=`live_api` answer=Based on live API evidence, the matching item(s) are: Welcome Journey.
- `journey_list_nested` source=`live_api` answer=Based on live API evidence, the matching item(s) are: Welcome Journey.
