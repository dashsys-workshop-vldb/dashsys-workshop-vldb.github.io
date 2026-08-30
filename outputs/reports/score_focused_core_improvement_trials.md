# Score-Focused Core Improvement Trials

Diagnostic-only answer/SQL-evidence trials over the direct score-producing path. No packaged runtime, official eval artifact, or final submission output is changed.

- Baseline strict score: `0.6553`
- Official score claim: `False`
- Writes eval outputs: `False`
- Writes final submission: `False`
- Recommendation: `keep_trial_only`

| Variant | Projected strict | Delta | Rows helped | Rows hurt | Unsupported delta | Promotion safe? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `sql_required_value_answer_slots` | 0.6553 | 0.0 | 3 | 4 | 0 | False |
| `zero_row_local_evidence_clarity` | 0.6499 | -0.0054 | 0 | 4 | 2 | False |
| `dry_run_caveat_after_sql_answer` | 0.6403 | -0.015 | 0 | 13 | 0 | False |
| `answer_intent_count_list_status_guard` | 0.6424 | -0.0129 | 0 | 11 | 2 | False |
| `combined_minimal` | 0.639 | -0.0163 | 0 | 14 | 0 | False |

## Fix Decision

No variant passed all isolated promotion gates; keep trial-only and make no runtime change.
