# Remaining Grounding Failure Triage

Generated: 2026-06-02T14:05:13.155528+00:00

Scope: original 8 non-timeout final semantic gate failures were rechecked after narrow answer-grounding fixes. `example_003` is analyzed separately as a contained timeout. No packaged default or promotion setting changed.

## Fresh Summary

- Previous non-timeout final gate failures: 8
- Fresh non-timeout final gate failures: 2
- Fresh failure types: {'missing_required_info': 2}
- Fresh timeout query IDs: ['example_003']
- Final unsupported claim rows after repair/fallback: 0
- Initial unsupported-claim diagnostics repaired or rejected: ['example_008', 'example_010', 'example_030']
- Conservative no-tool false positives: 0

## Target Rows

|Query|Prompt|Gate Passed|Current Error|Verdict|Note|Final Answer|
|---|---|---|---|---|---|---|
|example_001|Give me inactive journeys|True|missing_required_info|RESOLVED_FINAL_GATE|Composer fallback now includes requested status/filter slot for zero-row local evidence; final gate passes. Objective caveat: upstream evidence path still returns zero local rows, so this is not proof the planner foun...|Local snapshot evidence shows T1/SQL/LOCAL_SNAPSHOT: count: 0; status: inactive / T3/SQL_AND_API/LOCAL_SNAPSHOT: count: 0; status: inactive. Live API evidence was unavailable, so a live comparison cannot be completed.|
|example_004|Show me the IDs of failed dataflow runs|True||RESOLVED_GATE_FALSE_POSITIVE_BUT_OBJECTIVE_SCOPE_RISK|The previous contradiction was a claim-extractor false positive on negative/non-success wording. Final gate now passes, but the answer still exposes enabled-run examples for a failed-run prompt; this is an upstream ev...|The local snapshot contains 16 dataflow runs, but the available evidence only lists three records with an enabled state rather than failed ones. The specific IDs for these enabled runs are d02b782b-e586-454a-82df-7927...|
|example_012|List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.|False|missing_required_info|STILL_FAILS_TRUE_MISSING_INFO|Final answer still omits required relationship/mapping specificity for audiences mapped to new destinations; gate reports missing entity_names and pass:t4_segment_target_mapping.|Local snapshot evidence shows t2_segments_list/SQL/LOCAL_SNAPSHOT: count: 13; examples include Person: Birthday Today 001; Campaign: 25% Off Purchase Offer Reminder; Campaign: New Application Credit Card Offer; id: 2f...|
|example_017|Which tags belong to the category 'Uncategorized'?|True||RESOLVED_SAFE_API_CAVEAT|All required evidence is API-only and failed/unavailable; semantic gate now accepts the scoped unavailable caveat without requiring prompt-only category text as runtime output.|Runtime evidence was unavailable; cannot provide a verified answer.|
|example_018|Show me the details of the tag named 'cool'.|True||RESOLVED_SAFE_API_CAVEAT|All required evidence is API-only and failed/unavailable; semantic gate now accepts the scoped unavailable caveat without treating the prompt tag name as missing runtime evidence.|Runtime evidence was unavailable; cannot provide a verified answer.|
|example_021|Show the default merge policy for schema class '_xdm.context.profile'.|False|missing_required_info|STILL_FAILS_TRUE_MISSING_INFO|Final answer still does not identify the default merge policy for the requested schema class; local evidence includes related merge policy rows but the answer/composer does not satisfy the requested default-policy rel...|Local snapshot evidence shows t1_merge_policies/SQL/LOCAL_SNAPSHOT: count: 13; examples include Person: Birthday Today 001; Campaign: 25% Off Purchase Offer Reminder; Campaign: New Application Credit Card Offer; id: 2...|
|example_024|Which segment definitions were updated most recently?|True||RESOLVED_RANKED_RECENT_SUMMARY|Gate now allows a ranked most-recent answer that includes the top entity and timestamp instead of requiring every entity name from the candidate set.|The most recently updated segment definition is Person: Birthday Today 001, which was last updated on 2026-04-05T04:33:25.000+00:00.|
|example_027|Show all segment jobs with status 'QUEUED'.|True||RESOLVED_SAFE_API_CAVEAT|All required evidence is API-only and failed/unavailable; semantic gate now accepts the scoped unavailable caveat without requiring prompt-only QUEUED status as runtime output.|Runtime evidence was unavailable; cannot provide a verified answer.|

## Current Non-Timeout Final Gate Failures

|Query|Prompt|Error|Missing|Final Answer|
|---|---|---|---|---|
|example_012|List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.|missing_required_info|{"items": ["entity_names", "pass:t4_segment_target_mapping"], "total_items": 2, "truncated_items": false}|Local snapshot evidence shows t2_segments_list/SQL/LOCAL_SNAPSHOT: count: 13; examples include Person: Birthday Today 001; Campaign: 25% Off Purchase Offer Reminder; Campaign: New Application Credit Card Offer; id: 2f...|
|example_021|Show the default merge policy for schema class '_xdm.context.profile'.|missing_required_info|{"items": ["entity_names"], "total_items": 1, "truncated_items": false}|Local snapshot evidence shows t1_merge_policies/SQL/LOCAL_SNAPSHOT: count: 13; examples include Person: Birthday Today 001; Campaign: 25% Off Purchase Offer Reminder; Campaign: New Application Credit Card Offer; id: 2...|

## Timeout Analysis

|Query|Prompt|Timed Out|Stage|Analysis|
|---|---|---|---|---|
|example_003|List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit f...|True|checkpoint_llm_owned_dependency_resolution|Contained timeout remains separate from final answer grounding. The fresh eval timed out example_003 at dependency resolution; stale/partial trajectory content must not be counted as a non-timeout grounding failure.|
