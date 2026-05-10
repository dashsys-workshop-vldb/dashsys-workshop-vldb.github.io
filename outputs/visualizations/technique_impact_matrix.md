# Technique Impact Matrix

Metrics below are copied from current reports. Missing values are `unavailable`.

| Technique | Status | Promoted? | Strict Δ | Correctness Δ | Answer Δ | SQL Δ | API Δ | Token Δ | Runtime Δ | Tool Δ | Hidden-style impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SQL_FIRST_API_VERIFY packaged strategy | promoted_default | True | 0.0 | 0.0 | 0.3199 | 0.9333 | 0.9791 | 834.6 | 0.0117 | 1.4571 | 48/48 hidden-style in current report | current safe default |
| official-token reduction | promoted_default | True | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | 48/48 maintained | promoted_keep_enabled |
| supportable answer rewrite | shadow_only | False | -0.0001 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | no packaged effect | safe_for_autonomous_packaged_trial |
| evidence-aware answer candidates | shadow_only | False | -0.0059 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | no packaged effect | safe_for_autonomous_packaged_trial |
| autonomous packaged trial bundle | shadow_only | False | 0.0067 | 0.0067 | unavailable | unavailable | unavailable | -3.6571 | -0.001 | 0.0 | hidden-style gate passed | continue_iteration_target_not_reached |
| answer-shape v2 | default_off | False | 0.0006 | 0.0006 | -0.1162 | unavailable | unavailable | unavailable | unavailable | unavailable | hidden-style gate passed | safe_for_answer_shape_v2_trial |
| endpoint/schema rule canary | shadow_only | False | 0.0 | 0.0 | unavailable | unavailable | 0.0 | 0.0 | 0.0 | 0.0 | hidden-style gate passed | keep_shadow_only |
| endpoint-family tie-break v2 | shadow_only | False | 0 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | no packaged effect | keep_shadow_only |
| AST-guided SQL candidate canary | shadow_only | False | 0.0 | 0.0 | unavailable | unavailable | unavailable | 0.0 | 0.0 | 0.0 | no hidden-style effect reported | keep_shadow_only |
| local knowledge index | diagnostic_only | False | 0.0 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | no packaged effect | handoff_to_integration_for_candidate_selection |
| OpenRouter LLM answer rewrite search | shadow_only | False | 0 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | no packaged effect | keep_shadow_only |
| live-mode readiness | diagnostic_only | False | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | does not change dry-run behavior | diagnostic_only |
