# Hybrid Answer Scorer Feature Audit

This report mirrors scorer-visible features for audit only. Gold answers are not runtime inputs.

| Feature | Baseline | Hybrid |
|---|---:|---:|
| Avg fuzzy similarity | 0.4036 | 0.3135 |
| Avg token recall | 0.4291 | 0.3242 |
| Substring match count | 1 | 0 |

## Feature Loss Counts

|feature_loss|count|
|---|---|
|token_overlap|11|
|fuzzy_similarity|8|
|numeric_overlap|3|
|status_overlap|2|
|substring_match|1|

## Largest Feature-Loss Rows

|query_id|answer_delta|losses|prompt|
|---|---|---|---|
|example_011|-0.2356|token_overlap, fuzzy_similarity|How many schemas do I have?|
|example_010|-0.2283|substring_match, status_overlap, token_overlap, fuzzy_similarity|Count the number of XDM Experience Event schemas that are enabled for profile.|
|example_014|-0.1245|token_overlap, fuzzy_similarity|Show me all entities created by download|
|example_034|-0.1187|numeric_overlap, token_overlap, fuzzy_similarity|Show ingestion record counts and batch success counts for the last 90 days.|
|example_033|-0.1117|numeric_overlap, token_overlap|What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?|
|example_013|-0.0996|numeric_overlap, token_overlap, fuzzy_similarity|Show recent changes in datasets.|
|example_022|-0.0574|token_overlap, fuzzy_similarity|How many segment definitions exist in this sandbox?|
|example_003|-0.0265|token_overlap, fuzzy_similarity|List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updated...|
|example_024|-0.0227|token_overlap|Which segment definitions were updated most recently?|
|example_023|-0.0206|token_overlap, fuzzy_similarity|List all segment definitions.|
|example_000|0.0000||When was the journey 'Birthday Message' published?|
|example_001|0.0000||Give me inactive journeys|
