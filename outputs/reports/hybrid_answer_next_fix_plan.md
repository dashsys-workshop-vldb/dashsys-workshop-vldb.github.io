# Hybrid Answer Next Fix Plan

No implementation was performed in this audit pass.

## Top Root Causes

|root_cause|count|
|---|---|
|CANONICAL_RENDERER_WRONG_TEMPLATE|10|
|TEMPLATE_TOO_SHORT|8|
|FUZZY_SIMILARITY_DROP|8|
|WRONG_OBJECT_LABEL|4|
|MISSING_EXACT_NUMBER|3|

## Main Diagnosis

- Primary issue classification: `intent_router_plus_renderer`
- Recommended direction: `legacy_first_with_selective_hybrid_override`
- Detail: Keep SQL/API path unchanged. For organizer-style structured data, make legacy the default unless canonical rendering demonstrably preserves exact numbers/dates/status/entity substrings and does not add scope/caveat wording that hurts strict scorer features. Use hybrid canonical only for intents where feature audit shows equal-or-better overlap.

## Rows Most Responsible For Drop

|query_id|answer_score_delta|root_causes|prompt|
|---|---|---|---|
|example_011|-0.2356|['TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|How many schemas do I have?|
|example_010|-0.2283|['MISSING_STATUS_WORD', 'OVER_CAVEATED', 'TEMPLATE_TOO_SHORT', 'HYBRID_LOST_SUBSTRING_MATCH', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERE...|Count the number of XDM Experience Event schemas that are enabled for profile.|
|example_014|-0.1245|['ANSWER_INTENT_WRONG', 'ANSWER_MODE_WRONG', 'TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|Show me all entities created by download|
|example_034|-0.1187|['MISSING_EXACT_NUMBER', 'TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|Show ingestion record counts and batch success counts for the last 90 days.|
|example_033|-0.1117|['MISSING_EXACT_NUMBER', 'ANSWER_INTENT_WRONG', 'TEMPLATE_TOO_SHORT', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?|
|example_013|-0.0996|['MISSING_EXACT_NUMBER', 'WRONG_OBJECT_LABEL', 'TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|Show recent changes in datasets.|
|example_022|-0.0574|['WRONG_OBJECT_LABEL', 'TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|How many segment definitions exist in this sandbox?|
|example_003|-0.0265|['OVER_CAVEATED', 'TEMPLATE_TOO_SHORT', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updated...|
|example_024|-0.0227|['WRONG_OBJECT_LABEL', 'UNDER_CAVEATED', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|Which segment definitions were updated most recently?|
|example_023|-0.0206|['WRONG_OBJECT_LABEL', 'FUZZY_SIMILARITY_DROP', 'CANONICAL_RENDERER_WRONG_TEMPLATE']|List all segment definitions.|

## Proposed Next Fixes

- Add a runtime-evidence-only answer feature comparator that refuses hybrid when numeric/date/status/entity overlap is below legacy.
- Tune COUNT templates to preserve exact count and object label already emitted by legacy; avoid extra scope text unless local/live distinction is required by prompt or evidence conflict.
- Tune DATE/STATUS templates to keep entity name plus exact date/status fields from AnswerSlots; do not collapse date rows into generic status labels.
- For LIST rows, preserve legacy item ordering and identifiers when those appear in AnswerSlots; canonical semicolon formatting is acceptable only if it keeps all requested fields.
- Make canonical caveats scoped and short, but do not replace available SQL evidence with LIVE_EMPTY caveat when SQL_DIRECT_ANSWER exists and API is only empty scoped support.
- Adjust AnswerIntentRouter only for rows where audit_expected_answer_type differs from predicted intent; do not use gold-derived labels at runtime.

## Safety Constraints

- Do not change packaged default strategy.
- Do not change SQL/API planner, validators, or execution.
- Do not use gold/category/tags/oracle/query_id at runtime.
- Keep unsupported claims at 0 and preserve API_ERROR vs no-data and LIVE_EMPTY scoped semantics.
- Validate SQL/API call deltas remain 0 against SQL_FIRST_API_VERIFY for answer-only strategies.

## Minimal Test Plan

- Unit: legacy-first selector keeps legacy when hybrid loses exact count/date/status/entity overlap.
- Unit: canonical count/date/status/list templates preserve exact AnswerSlots values and requested roles.
- Unit: LIVE_EMPTY does not override available SQL_DIRECT_ANSWER as global no-data.
- Focused: run tests/test_gold_style_canonical_renderer.py tests/test_answer_intent_router.py tests/test_hybrid_answer_composer.py.
- Eval: run organizer35 only for SQL_FIRST_API_VERIFY and SQL_FIRST_API_VERIFY_HYBRID_ANSWER; require SQL/API/tool deltas 0 and unsupported claims 0.

- Promotion recommendation: `none`
