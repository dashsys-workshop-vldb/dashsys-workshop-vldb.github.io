# Semantic Router Feedback Loop Iteration 2

- Variant: `no_intent_application`
- Status: `complete`
- Outcome classification: `variant_failed`
- Recommendation: `do_not_promote`
- Strict delta: `-0.0032`
- Answer/SQL/API deltas: `0.0` / `0.0` / `0.0`
- Tool/token/runtime deltas: `0.0` / `377.0571` / `0.0087`
- Packaged runtime affected: `False`

## Lesson

no_intent_application did not beat the packaged baseline under isolated strict comparison.

## Helped Examples

- None identified.

## Hurt Or Risky Examples

- `example_003` delta=`-0.0033` answer_delta=`0.0` prompt="List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, cre"
- `example_013` delta=`-0.0035` answer_delta=`0.0` prompt="Show recent changes in datasets."
- `example_014` delta=`-0.0036` answer_delta=`0.0` prompt="Show me all entities created by download"
- `example_015` delta=`-0.0036` answer_delta=`0.0` prompt="How many tags exist in this sandbox?"
- `example_016` delta=`-0.0032` answer_delta=`0.0` prompt="List all tags in this sandbox."
- `example_017` delta=`-0.0034` answer_delta=`0.0` prompt="Which tags belong to the category 'Uncategorized'?"
