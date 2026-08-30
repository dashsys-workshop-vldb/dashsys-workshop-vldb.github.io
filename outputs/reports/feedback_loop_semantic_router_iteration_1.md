# Semantic Router Feedback Loop Iteration 1

- Variant: `narrow_eligibility`
- Status: `complete`
- Outcome classification: `variant_failed`
- Recommendation: `do_not_promote`
- Strict delta: `-0.0032`
- Answer/SQL/API deltas: `0.0` / `0.0` / `0.0`
- Tool/token/runtime deltas: `0.0` / `376.8286` / `0.011`
- Packaged runtime affected: `False`

## Lesson

narrow_eligibility did not beat the packaged baseline under isolated strict comparison.

## Helped Examples

- None identified.

## Hurt Or Risky Examples

- `example_014` delta=`-0.0036` answer_delta=`0.0` prompt="Show me all entities created by download"
- `example_016` delta=`-0.0033` answer_delta=`0.0` prompt="List all tags in this sandbox."
- `example_017` delta=`-0.0035` answer_delta=`0.0` prompt="Which tags belong to the category 'Uncategorized'?"
- `example_018` delta=`-0.0031` answer_delta=`0.0` prompt="Show me the details of the tag named 'cool'."
- `example_019` delta=`-0.0031` answer_delta=`0.0` prompt="List all merge policies in this sandbox."
- `example_028` delta=`-0.0033` answer_delta=`0.0` prompt="List the most recently created batches."
