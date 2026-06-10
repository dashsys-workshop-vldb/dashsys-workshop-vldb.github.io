# Evidence Usage Audit

Report-only audit of whether final answers use available SQL/API evidence. No runtime behavior changed.

- Status: `complete`
- Rows: `35`
- Official score claim: `False`

## Category Distribution

- `answer_missing_count`: `3`
- `answer_missing_names`: `2`
- `answer_missing_status`: `1`
- `answer_missing_timestamp`: `3`
- `answer_too_vague`: `13`
- `evidence_available_but_unused`: `2`
- `evidence_used_well`: `6`
- `unsupported_claim`: `3`
- `zero_row_answer_unclear`: `2`

## Examples

- `example_000` answer_missing_count: The journey "Birthday Message" has not been published.
- `example_001` answer_missing_timestamp: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31).
- `example_002` evidence_available_but_unused: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email.
- `example_003` unsupported_claim: Based on the evidence provided, there is no data available to answer this question.
- `example_004` zero_row_answer_unclear: Based on the evidence provided, there are no failed dataflow runs to report.
- `example_005` answer_missing_status: Based on the evidence provided, 1 destination was found.
- `example_006` evidence_used_well: Based on the evidence provided, 2 datasets have been ingested using the same schema.
- `example_007` unsupported_claim: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'.
