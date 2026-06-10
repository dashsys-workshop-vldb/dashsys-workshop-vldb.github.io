# Type-Specific Deterministic Rule Trials

Trials are isolated simulations and do not overwrite official eval or final submission artifacts.

- Baseline strict score: `0.6553`
- Runtime change applied: `False`
- Writes eval outputs: `False`
- Writes final submission: `False`

| Rule Family | Trial Type | Strict Delta | Tool Delta | API Dry-Run Reduction | Safe? |
| --- | --- | ---: | ---: | ---: | --- |
| `sql_only_fast_path` | `api_skip_shadow_trial` | `0.0` | `-46` | `46` | `True` |
| `count_answer_fast_path` | `answer_only_trial` | `0.0` | `0` | `0` | `True` |
| `list_name_id_answer_fast_path` | `answer_only_trial` | `0.0` | `0` | `0` | `True` |
| `status_date_answer_fast_path` | `answer_only_trial` | `0.0` | `0` | `0` | `True` |
| `zero_row_local_evidence_fast_path` | `answer_only_trial` | `-0.0007` | `0` | `0` | `False` |
| `api_caveat_suppression_reordering` | `answer_only_trial` | `0.0` | `0` | `0` | `False` |
| `unknown_ambiguous_safe_fallback` | `fast_path_runtime_simulation` | `0.0` | `-28` | `28` | `True` |
| `combined_safe_bucket_trial` | `combined_safe_bucket_trial` | `0.0` | `-69` | `69` | `True` |
