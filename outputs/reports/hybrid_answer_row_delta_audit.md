# Hybrid Answer Row Delta Audit

Organizer35 trajectories were reused; no eval rerun was needed.

| Metric | SQL_FIRST_API_VERIFY | SQL_FIRST_API_VERIFY_HYBRID_ANSWER | Delta |
|---|---:|---:|---:|
| Final | 0.6564 | 0.6477 | -0.0087 |
| Answer | 0.3207 | 0.293 | -0.0277 |
| SQL | 0.9333 | 0.9333 | 0.0 |
| API | 0.9791 | 0.9791 | 0.0 |
| Tool calls | 1.4571 | 1.4571 | 0.0 |

- Hybrid better/equal/worse: `1` / `24` / `10`
- Unsupported claims: `0`

## Root Cause Counts

|root_cause|count|
|---|---|
|CANONICAL_RENDERER_WRONG_TEMPLATE|10|
|TEMPLATE_TOO_SHORT|8|
|FUZZY_SIMILARITY_DROP|8|
|WRONG_OBJECT_LABEL|4|
|MISSING_EXACT_NUMBER|3|
|OVER_CAVEATED|2|
|ANSWER_INTENT_WRONG|2|
|MISSING_STATUS_WORD|1|
|HYBRID_LOST_SUBSTRING_MATCH|1|
|ANSWER_MODE_WRONG|1|
|UNDER_CAVEATED|1|

## Worst Rows

|query_id|answer_delta|intent|mode|root_causes|prompt|
|---|---|---|---|---|---|
|example_011|-0.2356|COUNT|CANONICAL_DATA|TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|How many schemas do I have?|
|example_010|-0.2283|COUNT|CANONICAL_DATA|MISSING_STATUS_WORD, OVER_CAVEATED, TEMPLATE_TOO_SHORT, HYBRID_LOST_SUBSTRING_MATCH, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMP...|Count the number of XDM Experience Event schemas that are enabled for profile.|
|example_014|-0.1245|ERROR_CAVEAT|CANONICAL_CAVEAT|ANSWER_INTENT_WRONG, ANSWER_MODE_WRONG, TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|Show me all entities created by download|
|example_034|-0.1187|COUNT|CANONICAL_DATA|MISSING_EXACT_NUMBER, TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|Show ingestion record counts and batch success counts for the last 90 days.|
|example_033|-0.1117|COUNT|CANONICAL_DATA|MISSING_EXACT_NUMBER, ANSWER_INTENT_WRONG, TEMPLATE_TOO_SHORT, CANONICAL_RENDERER_WRONG_TEMPLATE|What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?|
|example_013|-0.0996|LIST|CANONICAL_DATA|MISSING_EXACT_NUMBER, WRONG_OBJECT_LABEL, TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|Show recent changes in datasets.|
|example_022|-0.0574|COUNT|CANONICAL_DATA|WRONG_OBJECT_LABEL, TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|How many segment definitions exist in this sandbox?|
|example_003|-0.0265|COUNT|CANONICAL_DATA|OVER_CAVEATED, TEMPLATE_TOO_SHORT, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updated...|
|example_024|-0.0227|LIST|CANONICAL_DATA|WRONG_OBJECT_LABEL, UNDER_CAVEATED, CANONICAL_RENDERER_WRONG_TEMPLATE|Which segment definitions were updated most recently?|
|example_023|-0.0206|LIST|CANONICAL_DATA|WRONG_OBJECT_LABEL, FUZZY_SIMILARITY_DROP, CANONICAL_RENDERER_WRONG_TEMPLATE|List all segment definitions.|

Full per-row details are in the JSON report.
