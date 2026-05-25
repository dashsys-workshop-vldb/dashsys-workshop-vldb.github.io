# Controller Rewrite Policy Trial

Diagnostic-only artifact replay. No controller rewrite policy is promoted.

- Recommendation: `backend_answer_only_shadow_candidate`

## Variants

- `current_controller`: strict delta `0.0`, answer delta `0.0`, helped `0`, hurt `0`
- `backend_answer_only`: strict delta `0.0162`, answer delta `0.0584`, helped `20`, hurt `15`
- `verifier_forced_backend_safe`: strict delta `0.0195`, answer delta `0.0626`, helped `12`, hurt `2`
- `minimal_style_edit_only`: strict delta `0.0163`, answer delta `0.0586`, helped `20`, hurt `15`
- `no_rewrite_when_backend_complete`: strict delta `0.0125`, answer delta `0.0459`, helped `19`, hurt `15`
- `evidence_locked_rewrite`: strict delta `0.0195`, answer delta `0.0626`, helped `12`, hurt `2`
- `answer_shape_template_after_backend`: strict delta `0.0163`, answer delta `0.0586`, helped `20`, hurt `15`
