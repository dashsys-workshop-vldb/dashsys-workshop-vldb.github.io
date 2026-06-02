# Score Improvement Timeline

| Milestone | Score before | Score after | Score Δ | Changed | Promoted? | Why it mattered |
| --- | --- | --- | --- | --- | --- | --- |
| initial baseline | unavailable | unavailable | unavailable | LLM-free baseline comparison | False | Baseline only; not packaged. |
| SQL/API template improvements | unavailable | unavailable | unavailable | Reusable SQL/API templates and deterministic metadata path | False | Competitive but not preferred due to cost/risk tradeoff. |
| SQL_FIRST_API_VERIFY selection | unavailable | 0.6562 | unavailable | SQL-first grounding with API verification | True | Current preferred packaged strategy. |
| official-token reduction promotion | unavailable | unavailable | unavailable | Official token reduction enabled | True | unavailable |
| supportable answer rewrite | 0.6562 | 0.6552 | -0.001 | Evidence-cited answer-only rewrite candidates | False | safe_for_autonomous_packaged_trial |
| LLM rewrite search | 0.6562 | unavailable | unavailable | OpenRouter rewrite proposals with local validation | False | keep_shadow_only |
| answer-shape v2 | 0.6491 | 0.6497 | 0.0006 | Row-level answer-shape A/B | False | safe_for_answer_shape_v2_trial |
| endpoint-family tie-break v2 | 0.6562 | 0.6562 | 0.0 | Shadow endpoint divergence analysis | False | keep_shadow_only |
| live-mode readiness | unavailable | unavailable | unavailable | Credential/live API readiness diagnostic | False | diagnostic_only |
| autonomous packaged trials | 0.6491 | 0.6558 | 0.0067 | Isolated packaged-style bundle trial | False | continue_iteration_target_not_reached |

## Promoted vs Shadow vs Diagnostic

| State | Techniques |
| --- | --- |
| promoted_default | SQL_FIRST_API_VERIFY packaged strategy, official-token reduction |
| shadow_only | supportable answer rewrite, evidence-aware answer candidates, autonomous packaged trial bundle, endpoint/schema rule canary, endpoint-family tie-break v2, AST-guided SQL candidate canary, OpenRouter LLM answer rewrite search |
| default_off | answer-shape v2 |
| diagnostic_only | local knowledge index, live-mode readiness |
