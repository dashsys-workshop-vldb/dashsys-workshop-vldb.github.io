# Generated Diagnostic Prompt Suite

Diagnostic prompt coverage only; not official strict score.

- Total prompts: `250`
- Source examples: `35`
- Runtime behavior: generated prompts are not used by the packaged system.

## Sample Prompts

- `gen_0001` [paraphrase/journey_campaign/DATE]: Can you please when was the journey 'Birthday Message' published?
- `gen_0002` [paraphrase/journey_campaign/DATE]: Using the available DASHSys evidence, when was the journey 'Birthday Message' published.
- `gen_0003` [paraphrase/journey_campaign/DATE]: Find the relevant date or timestamp for: When was the journey 'Birthday Message' published.
- `gen_0004` [paraphrase/journey_campaign/STATUS]: Can you please give me inactive journeys?
- `gen_0005` [paraphrase/journey_campaign/STATUS]: Using the available DASHSys evidence, give me inactive journeys.
- `gen_0006` [paraphrase/journey_campaign/STATUS]: Check the status evidence for: Give me inactive journeys.
- `gen_0007` [paraphrase/journey_campaign/LIST]: Can you please list all journeys?
- `gen_0008` [paraphrase/journey_campaign/LIST]: Using the available DASHSys evidence, list all journeys.
- `gen_0009` [paraphrase/journey_campaign/LIST]: Return the matching journey campaign records for: List all journeys.
- `gen_0010` [paraphrase/segment_audience/COUNT]: Can you please list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.?
- `gen_0011` [paraphrase/segment_audience/COUNT]: Using the available DASHSys evidence, list all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results..
- `gen_0012` [paraphrase/segment_audience/COUNT]: Give me the count for this segment audience request: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results..
- `gen_0013` [paraphrase/dataflow_run/STATUS]: Can you please show me the IDs of failed dataflow runs?
- `gen_0014` [paraphrase/dataflow_run/STATUS]: Using the available DASHSys evidence, show me the IDs of failed dataflow runs.
- `gen_0015` [paraphrase/dataflow_run/STATUS]: Check the status evidence for: Show me the IDs of failed dataflow runs.
- `gen_0016` [paraphrase/destination_flow/LIST]: Can you please export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.?
- `gen_0017` [paraphrase/destination_flow/LIST]: Using the available DASHSys evidence, export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation..
- `gen_0018` [paraphrase/destination_flow/LIST]: Return the matching destination flow records for: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation..
- `gen_0019` [paraphrase/schema_dataset/COUNT]: Can you please how many datasets have been ingested using the same schema in the prod sandbox?
- `gen_0020` [paraphrase/schema_dataset/COUNT]: Using the available DASHSys evidence, how many datasets have been ingested using the same schema in the prod sandbox.
- `gen_0021` [paraphrase/schema_dataset/COUNT]: Give me the count for this schema dataset request: How many datasets have been ingested using the same schema in the prod sandbox.
- `gen_0022` [paraphrase/schema_dataset/LIST]: Can you please list all datasets that use the schema 'hkg_adls_profile_count_history'.?
- `gen_0023` [paraphrase/schema_dataset/LIST]: Using the available DASHSys evidence, list all datasets that use the schema 'hkg_adls_profile_count_history'..
- `gen_0024` [paraphrase/schema_dataset/LIST]: Return the matching schema dataset records for: List all datasets that use the schema 'hkg_adls_profile_count_history'..
- `gen_0025` [paraphrase/schema_dataset/LIST]: Can you please show me the field for Person: Birthday Today 001?
- `gen_0026` [paraphrase/schema_dataset/LIST]: Using the available DASHSys evidence, show me the field for Person: Birthday Today 001.
- `gen_0027` [paraphrase/schema_dataset/LIST]: Return the matching schema dataset records for: show me the field for Person: Birthday Today 001.
- `gen_0028` [paraphrase/schema_dataset/SUMMARY]: Can you please provide more details for the schema 'weRetail: Customer Actions'?
- `gen_0029` [paraphrase/schema_dataset/SUMMARY]: Using the available DASHSys evidence, provide more details for the schema 'weRetail: Customer Actions'.
- `gen_0030` [paraphrase/schema_dataset/SUMMARY]: I need a summary answer for this schema dataset question: Provide more details for the schema 'weRetail: Customer Actions'.
- `gen_0031` [paraphrase/schema_dataset/COUNT]: Can you please count the number of XDM Experience Event schemas that are enabled for profile.?
- `gen_0032` [paraphrase/schema_dataset/COUNT]: Using the available DASHSys evidence, count the number of XDM Experience Event schemas that are enabled for profile..
- `gen_0033` [paraphrase/schema_dataset/COUNT]: Give me the count for this schema dataset request: Count the number of XDM Experience Event schemas that are enabled for profile..
- `gen_0034` [paraphrase/schema_dataset/COUNT]: Can you please how many schemas do I have?
- `gen_0035` [paraphrase/schema_dataset/COUNT]: Using the available DASHSys evidence, how many schemas do I have.
- `gen_0036` [paraphrase/schema_dataset/COUNT]: Give me the count for this schema dataset request: How many schemas do I have.
- `gen_0037` [paraphrase/segment_audience/BOOLEAN]: Can you please list all audiences in the sandbox that have been mapped to new destinations in the last 3 months.?
- `gen_0038` [paraphrase/segment_audience/BOOLEAN]: Using the available DASHSys evidence, list all audiences in the sandbox that have been mapped to new destinations in the last 3 months..
- `gen_0039` [paraphrase/segment_audience/BOOLEAN]: I need a boolean answer for this segment audience question: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months..
- `gen_0040` [paraphrase/schema_dataset/DATE]: Can you please show recent changes in datasets.?
- ... 210 more prompts in `data/generated_prompt_suite.json`
