# Hybrid Answer Intent Router Audit

## Distribution

| Category | Counts |
|---|---|
| answer_intent | `{'STATUS': 4, 'LIST': 18, 'COUNT': 11, 'ERROR_CAVEAT': 2}` |
| answer_mode | `{'CANONICAL_DATA': 33, 'CANONICAL_CAVEAT': 2}` |
| selected_source | `{'LEGACY_SAFE_RENDERER': 24, 'DETERMINISTIC_FALLBACK': 9, 'HYBRID_CANONICAL_CAVEAT': 1, 'HYBRID_CANONICAL_DATA': 1}` |
| fallback | `{'true': 33, 'false': 2}` |

## Average Delta By Intent

|intent|avg_delta|avg_score|
|---|---|---|
|COUNT|-0.0707|0.2275|
|ERROR_CAVEAT|-0.0622|0.2439|
|LIST|-0.0037|0.3098|
|STATUS|0|0.4219|

## Suspicious Intent Rows

|query_id|answer_score_delta|predicted_answer_intent|predicted_answer_mode|expected_audit_only_answer_type|prompt|
|---|---|---|---|---|---|
|example_007|0.0000|LIST|CANONICAL_DATA|COUNT|List all datasets that use the schema 'hkg_adls_profile_count_history'.|
|example_009|0.0000|ERROR_CAVEAT|CANONICAL_CAVEAT|STATUS|Provide more details for the schema 'weRetail: Customer Actions'|
|example_014|-0.1245|ERROR_CAVEAT|CANONICAL_CAVEAT|LIST|Show me all entities created by download|
|example_025|0.0000|LIST|CANONICAL_DATA|STATUS|List all segment evaluation jobs.|
|example_028|0.0000|LIST|CANONICAL_DATA|STATUS|List the most recently created batches.|
|example_030|0.0000|LIST|CANONICAL_DATA|STATUS|Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.|
|example_032|0.0761|LIST|CANONICAL_DATA|STATUS|Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.|
|example_033|-0.1117|COUNT|CANONICAL_DATA|MIXED|What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?|
