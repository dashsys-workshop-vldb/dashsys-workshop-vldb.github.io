# Execute_Sql Correctness Candidates

- `SQL-C1` schema-aware column synonym expansion: keep_analysis_only (risk `medium`)
- `SQL-C2` aggregate/count correctness guard: trial_next (risk `medium`)
- `SQL-C3` join-path consistency checker: keep_analysis_only (risk `medium`)
- `SQL-C4` status/date field preservation: trial_next (risk `low`)
- `SQL-C5` zero-row fallback analysis: keep_analysis_only (risk `medium`)
- `SQL-C6` answer slot extraction from aggregate aliases: promote_if_gate_passes (risk `low`)
- `SQL-C7` SQL repair after validation failure: keep_analysis_only (risk `medium`)
