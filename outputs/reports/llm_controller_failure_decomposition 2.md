# LLM Controller Failure Decomposition

Diagnostic-only decomposition. The controller remains shadow-only and is not promoted automatically.

- Controller rows: `35`
- Controller strict score: `0.6328`
- Instrumentation gap count: `35`
- Safest next controller improvement: `Run backend-vs-LLM rewrite ablation; test no-rewrite and minimal style-edit controller variants.`

## Loss Category Distribution

- `controller_helped`: `9`
- `dry_run_caveat_loss`: `5`
- `router_loss`: `20`
- `verifier_loss`: `1`

## Examples Hurt

- `example_000` `router_loss`: When was the journey 'Birthday Message' published?
- `example_001` `router_loss`: Give me inactive journeys
- `example_002` `router_loss`: List all journeys
- `example_003` `router_loss`: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.
- `example_004` `router_loss`: Show me the IDs of failed dataflow runs
- `example_005` `router_loss`: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.
- `example_006` `router_loss`: How many datasets have been ingested using the same schema in the prod sandbox?
- `example_007` `router_loss`: List all datasets that use the schema 'hkg_adls_profile_count_history'.

## Instrumentation Note

- Raw pre-verifier proposed LLM answers are unavailable in existing artifacts; no runtime was rerun for this report.
