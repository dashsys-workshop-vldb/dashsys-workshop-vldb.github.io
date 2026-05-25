# No-Template SQL Mode Diagnostic

This report isolates robustness-audit rows where fixed SQL templates did not hit. It does not disable templates in packaged runtime.

- No-template rows: `1284`
- SQL validation pass rate: `1.0`
- SQL execution pass rate: `1.0`
- Failure distribution: `{'no_sql_gap': 792, 'none': 458, 'join_reasoning_gap': 27, 'count_distinct_gap': 7}`
- Promotable: `False`
