# Pareto Report

- Best correctness strategy: `SQL_FIRST_API_VERIFY`
- Best final-score strategy: `SQL_FIRST_API_VERIFY`
- Best efficiency strategy: `SQL_ONLY_BASELINE`
- Lowest tool-call strategy: `SQL_ONLY_BASELINE`
- Lowest token strategy: `SQL_ONLY_BASELINE`

## Template-First Correctness Gains Without Final Gain

## SQL_FIRST_API_VERIFY Unnecessary API Candidates
- example_000: 1 API call(s) / When was the journey 'Birthday Message' published?
- example_001: 1 API call(s) / Give me inactive journeys
- example_002: 1 API call(s) / List all journeys
- example_003: 2 API call(s) / List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- example_009: 1 API call(s) / Provide more details for the schema 'weRetail: Customer Actions'
- example_010: 1 API call(s) / Count the number of XDM Experience Event schemas that are enabled for profile.
- example_011: 1 API call(s) / How many schemas do I have?
- example_013: 1 API call(s) / Show recent changes in datasets.
- example_014: 1 API call(s) / Show me all entities created by download
- example_025: 1 API call(s) / List all segment evaluation jobs.
- example_033: 1 API call(s) / What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

## SQL_ONLY Enough But SQL_FIRST Called API
- example_000: SQL-only correctness 0.9205, SQL_FIRST API calls 1
- example_009: SQL-only correctness 0.8589, SQL_FIRST API calls 1

## Selected Ensemble Candidates
- generic_sql_first: 35
