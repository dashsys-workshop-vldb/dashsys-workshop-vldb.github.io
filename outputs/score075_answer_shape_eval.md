# Score075 Answer-Shape Eval

- Branch: `codex/score075-answer-shape`
- Baseline SHA: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Packaged execution changed: false
- Final submission changed: false
- Default-off/report-only: true
- Declared dependency: `codex/score075-robustness-leakage`
- Rows inspected: 35
- Supported candidate rows: 16
- Unavailable-in-dry-run candidate rows: 19
- Low answer-score target rows: 24
- Shape counts: {'count': 10, 'date': 6, 'detail': 7, 'list': 8, 'status': 4}

## Safety Boundary
- Candidates use SQL rows, live API payloads, selected non-secret endpoint params, and query-visible entities only.
- Dry-run API `result_preview` is not treated as payload evidence.
- Missing fields remain explicitly unavailable in dry-run mode.
- No scorer, hidden-style expectation, final submission, compact context, or repair execution change was made.

## Low Answer-Score Targets
- `example_003` `date` supported=false answer_score=0.3559: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- `example_011` `count` supported=true answer_score=0.3915: How many schemas do I have?
- `example_012` `list` supported=true answer_score=0.2124: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.
- `example_013` `detail` supported=true answer_score=0.1695: Show recent changes in datasets.
- `example_015` `count` supported=false answer_score=0.3681: How many tags exist in this sandbox?
- `example_016` `list` supported=false answer_score=0.3598: List all tags in this sandbox.
- `example_017` `list` supported=true answer_score=0.1246: Which tags belong to the category 'Uncategorized'?
- `example_018` `detail` supported=true answer_score=0.3685: Show me the details of the tag named 'cool'.
- `example_019` `list` supported=false answer_score=0.1049: List all merge policies in this sandbox.
- `example_020` `count` supported=false answer_score=0.1079: How many merge policies are configured in this sandbox?
- `example_021` `detail` supported=true answer_score=0.117: Show the default merge policy for schema class '_xdm.context.profile'.
- `example_022` `count` supported=false answer_score=0.1178: How many segment definitions exist in this sandbox?
- `example_023` `list` supported=false answer_score=0.1166: List all segment definitions.
- `example_024` `date` supported=false answer_score=0.1092: Which segment definitions were updated most recently?
- `example_025` `list` supported=false answer_score=0.1075: List all segment evaluation jobs.
- `example_026` `count` supported=false answer_score=0.1186: How many segment jobs are currently processing?
- `example_027` `status` supported=false answer_score=0.2415: Show all segment jobs with status 'QUEUED'.
- `example_028` `date` supported=false answer_score=0.1063: List the most recently created batches.
- `example_029` `count` supported=false answer_score=0.1047: How many batches have status 'success'?
- `example_030` `detail` supported=true answer_score=0.0989: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.
- `example_031` `list` supported=false answer_score=0.1055: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?
- `example_032` `status` supported=false answer_score=0.381: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.
- `example_033` `date` supported=true answer_score=0.3878: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?
- `example_034` `count` supported=false answer_score=0.3645: Show ingestion record counts and batch success counts for the last 90 days.

## Merge Recommendation
answer_shape_candidates_ready_for_integration_trial
