# Live API Efficiency Compression Trial

This diagnostic estimates safe live API token/runtime compression opportunities without changing runtime payload handling.

- API prompt rows: `202`
- Average tokens with API: `1117.6782`
- Average runtime with API: `0.7491`
- Recommendation: Keep trial-only. The safest next implementation candidate is compact_api_raw_preview, but it still needs strict/hidden/submission validation before promotion.

## Variants

- `compact_api_raw_preview`: affected `25`, token delta `medium_positive`, recommendation `implementation_candidate`
- `evidencebus_field_projection`: affected `52`, token delta `small_to_medium_positive`, recommendation `trial_only`
- `endpoint_family_summary_schema`: affected `65`, token delta `small_to_medium_positive`, recommendation `trial_only`
- `remove_unused_live_payload_fields_from_answer_context`: affected `150`, token delta `small_positive`, recommendation `trial_only`
- `compact_pagination_metadata`: affected `202`, token delta `small_positive`, recommendation `trial_only`
- `keep_full_raw_only_in_diagnostic_reports`: affected `25`, token delta `medium_positive`, recommendation `trial_only`
