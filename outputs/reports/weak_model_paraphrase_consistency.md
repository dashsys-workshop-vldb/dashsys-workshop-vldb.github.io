# Weak Model Paraphrase Consistency

Diagnostic-only consistency check over the weak generated-prompt diagnostic rows.

- Groups: `17`
- Consistency score: `0.8431`
- Slot stability: `0.7647`
- SQL table stability: `0.7647`
- API endpoint stability: `0.7647`
- Answer grounding stability: `0.8824`

## Worst Unstable Groups

- `example_009`: `0.1667` (slot_signature, evidence_need, selected_sql_table, endpoint_selected, answer_grounding)
- `example_010`: `0.1667` (slot_signature, selected_sql_table, endpoint_selected, answer_intent, answer_grounding)
- `example_011`: `0.5` (slot_signature, selected_sql_table, endpoint_selected)
- `example_012`: `0.5` (slot_signature, selected_sql_table, endpoint_selected)
- `example_001`: `1.0` ()
- `example_002`: `1.0` ()
- `example_003`: `1.0` ()
- `example_004`: `1.0` ()
- `example_005`: `1.0` ()
- `example_006`: `1.0` ()
