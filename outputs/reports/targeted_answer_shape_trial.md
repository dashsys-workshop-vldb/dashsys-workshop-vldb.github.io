# Targeted Answer Shape Trial

This is an isolated diagnostic. It does not enable broad answer rewriting and does not change SQL/API evidence.

- Eligible rows: `141`
- Best variant: `evidence_source_suffix_minimal`
- Recommendation: No runtime answer-shape fix applied in this pass; variants remain isolated diagnostics until strict/hidden/generated robustness gates are rerun.

## Variants

- `count_direct_first` helped `15`, risk `low`, tool delta `0`
- `list_compact_with_ids_when_present` helped `34`, risk `low`, tool delta `0`
- `status_direct_first` helped `45`, risk `low`, tool delta `0`
- `live_empty_clear_no_results` helped `0`, risk `low`, tool delta `0`
- `api_error_clear_but_not_no_data` helped `71`, risk `medium`, tool delta `0`
- `sql_api_conflict_explicit` helped `0`, risk `low`, tool delta `0`
- `evidence_source_suffix_minimal` helped `82`, risk `medium`, tool delta `0`
