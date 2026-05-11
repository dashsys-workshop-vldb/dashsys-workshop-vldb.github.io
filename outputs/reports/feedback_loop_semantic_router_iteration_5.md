# Semantic Router Feedback Loop Iteration 5

- Variant: `no_api_forcing`
- Status: `complete`
- Outcome classification: `variant_failed`
- Recommendation: `do_not_promote`
- Strict delta: `-0.0032`
- Answer/SQL/API deltas: `0.0` / `0.0` / `0.0`
- Tool/token/runtime deltas: `0.0` / `378.0857` / `0.0092`
- Packaged runtime affected: `False`

## Lesson

no_api_forcing mostly had no runtime effect, so LLM cost is hard to justify for packaged use.

## Helped Examples

- None identified.

## Hurt Or Risky Examples

- `example_003` delta=`-0.0033` answer_delta=`0.0` prompt="List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, cre"
- `example_014` delta=`-0.0035` answer_delta=`0.0` prompt="Show me all entities created by download"
- `example_015` delta=`-0.0036` answer_delta=`0.0` prompt="How many tags exist in this sandbox?"
- `example_016` delta=`-0.0033` answer_delta=`0.0` prompt="List all tags in this sandbox."
- `example_017` delta=`-0.0035` answer_delta=`0.0` prompt="Which tags belong to the category 'Uncategorized'?"
- `example_018` delta=`-0.0031` answer_delta=`0.0` prompt="Show me the details of the tag named 'cool'."
