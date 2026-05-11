# System Summary

- Preferred strategy: `SQL_FIRST_API_VERIFY`
- Packaged strict score: `0.6552`
- Best isolated score: `0.6558`
- Hidden-style: `48/48`
- Final submission ready: `True`
- Official-token reduction enabled: `True`
- Repair execution enabled: `False`
- Compact context enabled: `False`
- Final recommendation: `ready_to_submit_with_official_token_reduction`
- Live Adobe API readiness: `warning` (smoke `skipped_live_credentials_missing`, pipeline `skipped_live_credentials_missing`)
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`; packaged runtime affected: `False`
- Decision-stage feedback loops: stages mapped `20`, semantic-router recommendation `candidate_not_viable_after_feedback_loops`

## Workflow

- Prompt normalization and query analysis
- Metadata/context selection
- SQL_FIRST_API_VERIFY planning
- Validated SQL/API execution
- Evidence extraction, answer synthesis, verification, and packaging

## Source Reports

- `outputs/eval_results_strict.json`
- `outputs/winner_readiness_report.json`
- `outputs/hidden_style_eval.json`
- `outputs/official_token_reduction_promotion_report.json`
