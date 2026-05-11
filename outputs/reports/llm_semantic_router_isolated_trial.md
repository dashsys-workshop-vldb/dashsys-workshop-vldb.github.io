# LLM Semantic Router Isolated Trial

Diagnostic isolated non-shadow trial only. This report does not promote packaged runtime behavior.

- Status: `complete`
- Packaged runtime affected: `False`
- Backend/model: `[REDACTED]`
- SDK path used: `True`
- Total prompts: `35`
- Strict scoring status: `available`
- Baseline avg strict score: `0.6553`
- Trial avg strict score: `0.6521`
- Strict score delta: `-0.0032`
- Route/domain/intent changes: `2` / `0` / `0`
- SQL/API/answer changes: `0` / `0` / `0`
- Recommendation: `do_not_promote`

## Where Semantic Routing Helped

- No helped examples identified in this run.

## Where Semantic Routing Hurt Or Was Risky

- `example_003`: prompt="List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, cre"; deterministic=`SQL_ONLY/SEGMENT_AUDIENCE`; helper=`SQL_ONLY/segment_audience/LIST`; applied=`True`; delta=`-0.0032`; baseline_answer="Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, an"; trial_answer="Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, an"
- `example_013`: prompt="Show recent changes in datasets."; deterministic=`SQL_ONLY/DATASET_SCHEMA`; helper=`SQL_THEN_API/schema_dataset/WHEN`; applied=`True`; delta=`-0.0035`; baseline_answer="Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history,"; trial_answer="Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history,"
- `example_014`: prompt="Show me all entities created by download"; deterministic=`SQL_ONLY/UNKNOWN`; helper=`API_THEN_SQL/observability/LIST`; applied=`True`; delta=`-0.0035`; baseline_answer="Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and live API ver"; trial_answer="Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and live API ver"
- `example_015`: prompt="How many tags exist in this sandbox?"; deterministic=`API_ONLY/COUNT_AGGREGATION`; helper=`API_ONLY/tags/COUNT`; applied=`True`; delta=`-0.0035`; baseline_answer="The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe cre"; trial_answer="The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe cre"
- `example_016`: prompt="List all tags in this sandbox."; deterministic=`API_ONLY/UNKNOWN`; helper=`API_ONLY/tags/LIST`; applied=`True`; delta=`-0.0032`; baseline_answer="The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are "; trial_answer="The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are "

## Safety

- Safety failures: `0`
