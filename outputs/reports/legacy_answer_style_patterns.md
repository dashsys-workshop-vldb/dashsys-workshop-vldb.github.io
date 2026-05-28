# Legacy Answer Style Patterns

Rows where legacy answer beats hybrid were analyzed for reusable style patterns. This is audit-only and does not change templates.

| Pattern | Count |
|---|---:|
| Hybrid worse rows | 10 |
| Legacy shorter | 2 |
| Legacy substring beats hybrid | 1 |
| Hybrid added scope/caveat terms | 3 |
| Object label mismatch | 4 |

## Shape Pairs

|shape_pair|count|
|---|---|
|multi_sentence -> count_sentence|2|
|count_sentence -> count_sentence|4|
|date_sentence -> date_sentence|1|
|multi_sentence -> caveat_sentence|1|
|multi_sentence -> list_semicolon|2|

## Reusable Style Rules

- **count_answer_style**: Prefer the concise legacy pattern that includes the exact number and the object label from the prompt/gold-like domain wording. Add local/live scope only when asked or when evidence conflict requires it.
- **date_answer_style**: Preserve entity name and exact timestamp/date field; avoid converting a date question into generic status wording.
- **status_answer_style**: Use entity plus explicit status word. Do not infer status labels from timestamp field names such as created/updated/published unless that field is the actual requested fact.
- **list_answer_style**: Keep semicolon-separated compact lists only when all requested fields remain present. Do not replace available SQL list evidence with scoped live-empty caveats.
- **caveat_style**: Keep caveats short and scoped; API_ERROR means unavailable/error, LIVE_EMPTY means no matching live records for that query/scope, not global absence.
- **local_live_scope_wording**: Mention local snapshot only when the prompt or evidence boundary requires it; avoid extra scope words in strict answer rows where legacy already matches better.
