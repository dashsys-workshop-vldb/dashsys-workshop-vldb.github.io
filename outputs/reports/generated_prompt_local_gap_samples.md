# Generated Prompt Local Gap Samples

Diagnostic-only sampler for local dry-run generated prompts. Generated labels may be noisy and are not official score evidence.

- Source prompts: `250` / `250`
- Official score claim: `False`

## route_mismatch

- Total count: `86`
- Top domains: `{'schema_dataset': 29, 'destination_flow': 15, 'segment_audience': 14, 'journey_campaign': 9, 'dataflow_run': 9, 'observability': 8, 'tags': 1, 'unknown': 1}`

- `gen_0007` cause=`live_api_required` action=`wait_for_live_api` prompt='Can you please list all journeys?'
- `gen_0008` cause=`live_api_required` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, list all journeys.'
- `gen_0009` cause=`live_api_required` action=`wait_for_live_api` prompt='Return the matching journey campaign records for: List all journeys.'
- `gen_0010` cause=`live_api_required` action=`wait_for_live_api` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, tot"
- `gen_0011` cause=`live_api_required` action=`wait_for_live_api` prompt="Using the available DASHSys evidence, list all segment audiences connected to the destination named 'SMS Opt-In', showin"

## domain_mismatch

- Total count: `177`
- Top domains: `{'schema_dataset': 57, 'batch': 31, 'tags': 23, 'destination_flow': 22, 'dataflow_run': 17, 'merge_policy': 16, 'observability': 9, 'segment_audience': 1, 'unknown': 1}`

- `gen_0013` cause=`synonym_gap` action=`add_synonym_candidate` prompt='Can you please show me the IDs of failed dataflow runs?'
- `gen_0014` cause=`synonym_gap` action=`add_synonym_candidate` prompt='Using the available DASHSys evidence, show me the IDs of failed dataflow runs.'
- `gen_0015` cause=`synonym_gap` action=`add_synonym_candidate` prompt='Check the status evidence for: Show me the IDs of failed dataflow runs.'
- `gen_0016` cause=`synonym_gap` action=`add_synonym_candidate` prompt='Can you please export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including al'
- `gen_0017` cause=`synonym_gap` action=`add_synonym_candidate` prompt='Using the available DASHSys evidence, export a list of all destinations in the b2b-prod sandbox, sorted by most recently'

## answer_intent_mismatch

- Total count: `154`
- Top domains: `{'schema_dataset': 38, 'segment_audience': 21, 'destination_flow': 20, 'batch': 20, 'journey_campaign': 16, 'tags': 11, 'dataflow_run': 11, 'merge_policy': 7, 'observability': 5, 'unknown': 5}`

- `gen_0001` cause=`generated_label_noise` action=`no_code_change` prompt="Can you please when was the journey 'Birthday Message' published?"
- `gen_0002` cause=`generated_label_noise` action=`no_code_change` prompt="Using the available DASHSys evidence, when was the journey 'Birthday Message' published."
- `gen_0003` cause=`generated_label_noise` action=`no_code_change` prompt="Find the relevant date or timestamp for: When was the journey 'Birthday Message' published."
- `gen_0010` cause=`answer_intent_gap` action=`add_intent_rule_candidate` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, tot"
- `gen_0011` cause=`answer_intent_gap` action=`add_intent_rule_candidate` prompt="Using the available DASHSys evidence, list all segment audiences connected to the destination named 'SMS Opt-In', showin"

## missing_count_or_name_advisory

- Total count: `89`
- Top domains: `{'segment_audience': 24, 'schema_dataset': 13, 'tags': 13, 'journey_campaign': 12, 'merge_policy': 10, 'batch': 8, 'destination_flow': 6, 'observability': 2, 'dataflow_run': 1}`

- `gen_0007` cause=`live_api_required` action=`wait_for_live_api` prompt='Can you please list all journeys?'
- `gen_0008` cause=`live_api_required` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, list all journeys.'
- `gen_0009` cause=`live_api_required` action=`wait_for_live_api` prompt='Return the matching journey campaign records for: List all journeys.'
- `gen_0010` cause=`live_api_required` action=`wait_for_live_api` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, tot"
- `gen_0011` cause=`live_api_required` action=`wait_for_live_api` prompt="Using the available DASHSys evidence, list all segment audiences connected to the destination named 'SMS Opt-In', showin"

## zero_row_sql

- Total count: `23`
- Top domains: `{'dataflow_run': 6, 'schema_dataset': 6, 'segment_audience': 4, 'journey_campaign': 3, 'destination_flow': 3, 'observability': 1}`

- `gen_0010` cause=`schema_or_sql_gap` action=`review_schema_mapping` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, tot"
- `gen_0011` cause=`schema_or_sql_gap` action=`review_schema_mapping` prompt="Using the available DASHSys evidence, list all segment audiences connected to the destination named 'SMS Opt-In', showin"
- `gen_0012` cause=`schema_or_sql_gap` action=`review_schema_mapping` prompt="Give me the count for this segment audience request: List all segment audiences connected to the destination named 'SMS "
- `gen_0013` cause=`schema_or_sql_gap` action=`review_schema_mapping` prompt='Can you please show me the IDs of failed dataflow runs?'
- `gen_0014` cause=`schema_or_sql_gap` action=`review_schema_mapping` prompt='Using the available DASHSys evidence, show me the IDs of failed dataflow runs.'

## requires_live_api

- Total count: `202`
- Top domains: `{'schema_dataset': 47, 'segment_audience': 32, 'batch': 31, 'journey_campaign': 28, 'tags': 22, 'destination_flow': 17, 'merge_policy': 16, 'dataflow_run': 6, 'observability': 2, 'unknown': 1}`

- `gen_0001` cause=`live_api_required` action=`wait_for_live_api` prompt="Can you please when was the journey 'Birthday Message' published?"
- `gen_0002` cause=`live_api_required` action=`wait_for_live_api` prompt="Using the available DASHSys evidence, when was the journey 'Birthday Message' published."
- `gen_0003` cause=`live_api_required` action=`wait_for_live_api` prompt="Find the relevant date or timestamp for: When was the journey 'Birthday Message' published."
- `gen_0004` cause=`live_api_required` action=`wait_for_live_api` prompt='Can you please give me inactive journeys?'
- `gen_0005` cause=`live_api_required` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, give me inactive journeys.'
