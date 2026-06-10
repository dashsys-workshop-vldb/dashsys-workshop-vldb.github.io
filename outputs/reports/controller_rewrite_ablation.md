# Controller Rewrite Ablation

Artifact-based replay only. No SQL/API rerun, no new LLM calls, and no automatic promotion.

- Controller rows: `35`
- Recommendation: `controller_no_rewrite_better`
- Backend SQL/API behavior preserved: `True`
- Backend evidence preserved: `True`

## Variants

- `backend_answer_only`: answer delta `0.0584`, final delta `0.0162`, helped `20`, hurt `15`
- `llm_rewrite_current`: answer delta `0.0`, final delta `0.0`, helped `0`, hurt `0`
- `verifier_forced_backend_safe`: answer delta `0.0626`, final delta `0.0195`, helped `12`, hurt `2`
- `minimal_llm_style_edit`: answer delta `0.0586`, final delta `0.0163`, helped `20`, hurt `15`
- `no_rewrite_when_backend_answer_complete`: answer delta `0.0459`, final delta `0.0125`, helped `19`, hurt `15`

## Recommendation

- Keep the controller shadow-only; any future promotion requires explicit strict, hidden-style, readiness, and safety gates.
