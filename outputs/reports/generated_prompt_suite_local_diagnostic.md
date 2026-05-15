# Generated Prompt Suite Local Diagnostic

Diagnostic coverage only. This local run forces Adobe API calls into dry-run mode and is not official strict-score evidence.

- Total prompts: `250`
- Executed prompts: `250`
- Runtime pass count: `250`
- Runtime fail count: `0`
- Validation fail count: `0`
- Dry-run API call count: `212`
- Zero-row SQL count: `23`
- Vague-answer advisory count: `0`
- Missing count/name advisory count: `89`
- Official score claim: `False`
- Promotion allowed: `False`
- No safe deterministic improvement applied: `True`

## Top Failure Categories

- `answer_intent_mismatch`: `88`
- `ok`: `4`
- `requires_live_api`: `71`
- `route_mismatch`: `86`
- `zero_row_sql`: `1`

## Candidate Groups Requiring Review

- `route_mismatch` / `schema_dataset`: `29` advisory cases
- `route_mismatch` / `destination_flow`: `15` advisory cases
- `route_mismatch` / `segment_audience`: `14` advisory cases
- `route_mismatch` / `journey_campaign`: `9` advisory cases
- `route_mismatch` / `dataflow_run`: `9` advisory cases
- `route_mismatch` / `observability`: `8` advisory cases
- `domain_mismatch` / `schema_dataset`: `57` advisory cases
- `domain_mismatch` / `batch`: `31` advisory cases
- `domain_mismatch` / `tags`: `23` advisory cases
- `domain_mismatch` / `destination_flow`: `22` advisory cases
- `domain_mismatch` / `dataflow_run`: `17` advisory cases
- `domain_mismatch` / `merge_policy`: `16` advisory cases
- `domain_mismatch` / `observability`: `9` advisory cases
- `zero_row_sql` / `dataflow_run`: `6` advisory cases
- `zero_row_sql` / `schema_dataset`: `6` advisory cases
- `zero_row_sql` / `segment_audience`: `4` advisory cases
- `zero_row_sql` / `journey_campaign`: `3` advisory cases
- `zero_row_sql` / `destination_flow`: `3` advisory cases
- `answer_template` / `segment_audience:COUNT`: `10` advisory cases
- `answer_template` / `journey_campaign:LIST`: `9` advisory cases

Heuristics in this report are advisory only and cannot support promotion or official score claims.
