# Local Gap Manual Review

Diagnostic-only manual review. Generated labels are advisory and are not treated as ground truth.

- Source prompts: `250` / `250`
- Official score claim: `False`
- Promotion allowed: `False`

## zero_row_sql / dataflow_run

- Total count: `6`
- Reviewed count: `6`
- True bug count: `0`
- Generated-label noise count: `0`
- Live API required count: `5`
- Implementation candidate: `False`
- Proposed minimal fix: No runtime change; wait for live API access or review after live_success.

- `gen_0013` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Can you please show me the IDs of failed dataflow runs?'
- `gen_0014` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, show me the IDs of failed dataflow runs.'
- `gen_0015` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Check the status evidence for: Show me the IDs of failed dataflow runs.'
- `gen_0150` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Show failed dataflow runs.'
- `gen_0153` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Which dataflow runs are currently in a failed state?'

## missing_count_or_name_advisory / segment_audience

- Total count: `24`
- Reviewed count: `10`
- True bug count: `0`
- Generated-label noise count: `0`
- Live API required count: `10`
- Implementation candidate: `False`
- Proposed minimal fix: No runtime change; wait for live API access or review after live_success.

- `gen_0010` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing a"
- `gen_0011` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, list all segment audiences connected to the destination named '
- `gen_0012` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Give me the count for this segment audience request: List all segment audiences connected to the des'
- `gen_0037` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Can you please list all audiences in the sandbox that have been mapped to new destinations in the la'
- `gen_0038` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, list all audiences in the sandbox that have been mapped to new'

## answer_intent_mismatch / segment_audience

- Total count: `21`
- Reviewed count: `10`
- True bug count: `0`
- Generated-label noise count: `6`
- Live API required count: `4`
- Implementation candidate: `False`
- Proposed minimal fix: No runtime change; generated label appears noisy for reviewed examples.

- `gen_0010` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt="Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing a"
- `gen_0011` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, list all segment audiences connected to the destination named '
- `gen_0012` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Give me the count for this segment audience request: List all segment audiences connected to the des'
- `gen_0037` cause=`generated_label_noise` true_bug=`False` action=`no_code_change` prompt='Can you please list all audiences in the sandbox that have been mapped to new destinations in the la'
- `gen_0038` cause=`generated_label_noise` true_bug=`False` action=`no_code_change` prompt='Using the available DASHSys evidence, list all audiences in the sandbox that have been mapped to new'

## domain_mismatch / dataflow_run

- Total count: `17`
- Reviewed count: `10`
- True bug count: `4`
- Generated-label noise count: `0`
- Live API required count: `6`
- Implementation candidate: `False`
- Proposed minimal fix: No runtime change; wait for live API access or review after live_success.

- `gen_0013` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Can you please show me the IDs of failed dataflow runs?'
- `gen_0014` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Using the available DASHSys evidence, show me the IDs of failed dataflow runs.'
- `gen_0015` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Check the status evidence for: Show me the IDs of failed dataflow runs.'
- `gen_0150` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Show failed dataflow runs.'
- `gen_0151` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Count failed flow runs in the available evidence.'

## route_mismatch / destination_flow

- Total count: `15`
- Reviewed count: `10`
- True bug count: `2`
- Generated-label noise count: `0`
- Live API required count: `8`
- Implementation candidate: `False`
- Proposed minimal fix: No runtime change; wait for live API access or review after live_success.

- `gen_0140` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='List destinations and their flow IDs.'
- `gen_0142` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Show flows by state for destinations.'
- `gen_0143` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Find destination metadata for a named target.'
- `gen_0144` cause=`synonym_gap` true_bug=`True` action=`add_synonym_candidate` prompt='List recently modified destination flows.'
- `gen_0145` cause=`live_api_required` true_bug=`False` action=`wait_for_live_api` prompt='Distinguish source flows from destination flows.'

## Recommended Next Human Review

- Category: `missing_count_or_name_advisory / segment_audience`
- Why: Largest reviewed high-value category; inspect examples before any runtime change.
- Can be fixed before Adobe access: `False`
