# Deterministic Prompt-Type Audit

This report groups official strict rows and diagnostic generated prompts by prompt intent, domain, execution need, and evidence shape.

- Official rows: `35`
- Generated prompts: `250`
- Fast-path candidate buckets: `33`
- Runtime change applied: `False`

| Bucket | Official | Generated | Fast Path? | Risk |
| --- | ---: | ---: | --- | --- |
| `count__count_aggregation__live_api_required` | `4` | `13` | `False` | `high` |
| `list_name_id__unknown__live_api_required` | `4` | `11` | `False` | `high` |
| `list_name_id__segment_audience__live_api_required` | `4` | `7` | `False` | `high` |
| `count__dataset_schema__live_api_required` | `3` | `9` | `False` | `high` |
| `count__segment_audience__live_api_required` | `3` | `7` | `False` | `high` |
| `unknown_ambiguous__unknown__live_api_required` | `3` | `0` | `False` | `high` |
| `timestamp_date_when__segment_audience__live_api_required` | `2` | `0` | `False` | `high` |
| `unknown_ambiguous__segment_audience__live_api_required` | `2` | `0` | `False` | `high` |
| `status__journey_campaign__live_api_required` | `1` | `6` | `False` | `high` |
| `list_name_id__journey_campaign__live_api_required` | `1` | `4` | `False` | `high` |
| `status__status_monitoring__live_api_required` | `1` | `4` | `False` | `high` |
| `status__destination_dataflow__live_api_required` | `1` | `3` | `False` | `high` |
| `unknown_ambiguous__property_field__sql_only_possible` | `1` | `1` | `False` | `medium` |
| `timestamp_date_when__dataset_schema__live_api_required` | `1` | `0` | `False` | `high` |
| `timestamp_date_when__destination_dataflow__live_api_required` | `1` | `0` | `False` | `high` |
| `timestamp_date_when__journey_campaign__live_api_required` | `1` | `0` | `False` | `high` |
| `timestamp_date_when__unknown__live_api_required` | `1` | `0` | `False` | `high` |
| `unknown_ambiguous__dataset_schema__live_api_required` | `1` | `0` | `False` | `high` |
| `unknown_ambiguous__unknown__api_required` | `0` | `20` | `True` | `medium` |
| `unknown_ambiguous__dataset_schema__dry_run_only_currently` | `0` | `8` | `False` | `medium` |
| `unknown_ambiguous__destination_dataflow__sql_only_possible` | `0` | `8` | `False` | `medium` |
| `count__dataset_schema__dry_run_only_currently` | `0` | `7` | `True` | `medium` |
| `unknown_ambiguous__destination_dataflow__dry_run_only_currently` | `0` | `7` | `True` | `medium` |
| `unknown_ambiguous__segment_audience__dry_run_only_currently` | `0` | `7` | `False` | `medium` |
| `unknown_ambiguous__unknown__sql_only_possible` | `0` | `7` | `False` | `medium` |
| `list_name_id__journey_campaign__dry_run_only_currently` | `0` | `6` | `True` | `medium` |
| `timestamp_date_when__journey_campaign__dry_run_only_currently` | `0` | `6` | `True` | `medium` |
| `list_name_id__unknown__api_required` | `0` | `5` | `True` | `medium` |
| `status__journey_campaign__sql_only_possible` | `0` | `5` | `True` | `medium` |
| `count__segment_audience__sql_only_possible` | `0` | `4` | `True` | `medium` |
| `list_name_id__destination_dataflow__dry_run_only_currently` | `0` | `4` | `True` | `medium` |
| `list_name_id__segment_audience__dry_run_only_currently` | `0` | `4` | `True` | `medium` |
| `status__journey_campaign__dry_run_only_currently` | `0` | `4` | `True` | `medium` |
| `status__status_monitoring__api_required` | `0` | `4` | `False` | `medium` |
| `timestamp_date_when__segment_audience__dry_run_only_currently` | `0` | `4` | `True` | `medium` |
| `unknown_ambiguous__journey_campaign__dry_run_only_currently` | `0` | `4` | `True` | `medium` |
| `count__count_aggregation__api_required` | `0` | `3` | `True` | `medium` |
| `count__segment_audience__dry_run_only_currently` | `0` | `3` | `True` | `medium` |
| `list_name_id__segment_audience__api_required` | `0` | `3` | `False` | `low` |
| `list_name_id__unknown__sql_only_possible` | `0` | `3` | `False` | `medium` |
| `status__destination_dataflow__dry_run_only_currently` | `0` | `3` | `True` | `medium` |
| `timestamp_date_when__dataset_schema__api_required` | `0` | `3` | `True` | `medium` |
| `timestamp_date_when__destination_dataflow__dry_run_only_currently` | `0` | `3` | `True` | `medium` |
| `timestamp_date_when__destination_dataflow__sql_only_possible` | `0` | `3` | `True` | `medium` |
| `timestamp_date_when__segment_audience__api_required` | `0` | `3` | `True` | `low` |
| `timestamp_date_when__unknown__api_required` | `0` | `3` | `True` | `medium` |
| `yes_no__unknown__api_required` | `0` | `3` | `False` | `medium` |
| `count__count_aggregation__sql_only_possible` | `0` | `2` | `True` | `medium` |
| `count__destination_dataflow__live_api_required` | `0` | `2` | `False` | `medium` |
| `list_name_id__dataset_schema__live_api_required` | `0` | `2` | `False` | `medium` |
| `list_name_id__dataset_schema__sql_only_possible` | `0` | `2` | `True` | `medium` |
| `list_name_id__segment_audience__sql_only_possible` | `0` | `2` | `True` | `medium` |
| `list_name_id__status_monitoring__live_api_required` | `0` | `2` | `False` | `medium` |
| `status__destination_dataflow__sql_only_possible` | `0` | `2` | `True` | `medium` |
| `status__journey_campaign__api_required` | `0` | `2` | `False` | `medium` |
| `status__status_monitoring__sql_only_possible` | `0` | `2` | `True` | `medium` |
| `unknown_ambiguous__dataset_schema__sql_only_possible` | `0` | `2` | `False` | `medium` |
| `count__dataset_schema__sql_only_possible` | `0` | `1` | `False` | `medium` |
| `list_name_id__dataset_schema__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
| `status__segment_audience__sql_only_possible` | `0` | `1` | `True` | `low` |
| `status__unknown__live_api_required` | `0` | `1` | `False` | `medium` |
| `timestamp_date_when__dataset_schema__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
| `timestamp_date_when__status_monitoring__api_required` | `0` | `1` | `False` | `medium` |
| `timestamp_date_when__unknown__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
| `unknown_ambiguous__count_aggregation__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
| `unknown_ambiguous__dataset_schema__api_required` | `0` | `1` | `False` | `medium` |
| `unknown_ambiguous__segment_audience__api_required` | `0` | `1` | `False` | `medium` |
| `unknown_ambiguous__segment_audience__sql_only_possible` | `0` | `1` | `False` | `medium` |
| `unknown_ambiguous__unknown__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
| `yes_no__dataset_schema__dry_run_only_currently` | `0` | `1` | `False` | `medium` |
| `yes_no__property_field__sql_only_possible` | `0` | `1` | `False` | `medium` |
| `yes_no__segment_audience__api_required` | `0` | `1` | `False` | `medium` |
| `yes_no__segment_audience__dry_run_only_currently` | `0` | `1` | `False` | `medium` |
| `yes_no__segment_audience__sql_only_possible` | `0` | `1` | `False` | `medium` |
| `yes_no__unknown__dry_run_only_currently` | `0` | `1` | `True` | `medium` |
