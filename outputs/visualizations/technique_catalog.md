# DASHSys Technique Catalog

Every technique below is tied to source artifacts. Missing measurements are marked `unavailable` rather than inferred.

| Technique | Category | Stage | State | Strict Δ | Correctness Δ | Token Δ | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- |
| query_normalizer | Query understanding / routing | query understanding | promoted_default | unavailable | unavailable | unavailable | Deterministic preprocessing; retained as core routing support. |
| query_tokens | Query understanding / routing | query understanding | promoted_default | unavailable | unavailable | unavailable | Low-cost deterministic signal used by ranking and templates. |
| relevance_scorer | Query understanding / routing | candidate ranking | promoted_default | unavailable | unavailable | unavailable | Core ranking signal; effects are embedded in current packaged metrics. |
| plan_ensemble | Query understanding / routing | planning | promoted_default | unavailable | unavailable | unavailable | Preserves deterministic single-plan execution. |
| metadata_selector | Query understanding / routing | context selection | promoted_default | unavailable | unavailable | unavailable | Needed to keep prompt context compact and deterministic. |
| query_analysis | Query understanding / routing | query analysis | promoted_default | unavailable | unavailable | unavailable | Core deterministic intent layer. |
| prompt_router | Query understanding / routing | routing | promoted_default | unavailable | unavailable | unavailable | Promoted as routing safety layer. |
| SQL_FIRST_API_VERIFY | Planning / execution | strategy | promoted_default | 0.0 | 0.0 | 797.9429 | Best current strict score and correctness among packaged strategies. |
| SQL templates | Planning / execution | SQL planning | promoted_default | unavailable | unavailable | unavailable | Reusable templates are part of current SQL score. |
| API templates | Planning / execution | API planning | promoted_default | unavailable | unavailable | unavailable | Reusable endpoint templates drive current API score. |
| planner | Planning / execution | planning | promoted_default | unavailable | unavailable | unavailable | Core packaged execution path. |
| executor | Planning / execution | execution | promoted_default | unavailable | unavailable | unavailable | Required packaged runtime component. |
| endpoint catalog | Planning / execution | API validation | promoted_default | unavailable | unavailable | unavailable | Safety boundary for API calls. |
| endpoint family ranker | Planning / execution | endpoint ranking | promoted_default | unavailable | unavailable | unavailable | Ranking is used; broader tie-break changes were not promoted. |
| endpoint-schema rule candidates | Planning / execution | endpoint/schema routing | shadow_only | 0.0 | 0.0 | 0.0 | Kept shadow-only because measurable improvement was false. |
| candidate generation | Planning / execution | candidate search | shadow_only | unavailable | unavailable | unavailable | No broad runtime promotion; used for diagnostics/trials. |
| execution-based candidate selector | Planning / execution | candidate search | shadow_only | unavailable | unavailable | unavailable | Kept isolated unless trial gates pass. |
| answer-shape v2 | Planning / execution | answer synthesis | default_off | 0.0006 | 0.0006 | unavailable | Not a packaged default; isolated trial was below 0.75 target. |
| supportable answer rewriter | Planning / execution | answer synthesis | shadow_only | -0.0069 | unavailable | unavailable | Safe rows feed isolated trials; not final promoted behavior. |
| SQL-only API-skip guard | Planning / execution | pre-execution guard | default_off | unavailable | unavailable | unavailable | Not promoted; conservative guard available behind flag only. |
| official-token reduction | Evidence / context / optimization | context optimization | promoted_default | unavailable | unavailable | unavailable | Promoted because strict score tied/improved safely with large token reduction. |
| local knowledge index | Evidence / context / optimization | evidence retrieval | diagnostic_only | 0.0 | unavailable | unavailable | Coverage exists, but score impact is currently 0. |
| cache | Evidence / context / optimization | retrieval optimization | promoted_default | unavailable | unavailable | unavailable | Infrastructure; no standalone score claim. |
| evidence_bus | Evidence / context / optimization | evidence collection | promoted_default | unavailable | unavailable | unavailable | Safety layer for supportable answers. |
| context cards | Evidence / context / optimization | context selection | promoted_default | unavailable | unavailable | unavailable | Core compact context mechanism. |
| fast paths | Evidence / context / optimization | planning optimization | promoted_default | unavailable | unavailable | unavailable | Efficiency-oriented infrastructure. |
| call budget | Evidence / context / optimization | planning optimization | promoted_default | unavailable | unavailable | unavailable | Keeps tool calls within packaged efficiency target. |
| evidence policy | Evidence / context / optimization | evidence gating | promoted_default | unavailable | unavailable | unavailable | Promoted core safety/answerability gate. |
| plan optimizer | Evidence / context / optimization | planning optimization | promoted_default | unavailable | unavailable | unavailable | Efficiency and safety support for packaged strategy. |
| compact context experiment | Evidence / context / optimization | context optimization | default_off | unavailable | unavailable | unavailable | Not promoted under current safety constraints. |
| shadow repair | Evidence / context / optimization | repair diagnostics | shadow_only | unavailable | unavailable | unavailable | Not promoted because repaired candidates did not pass gates. |
| AST-guided SQL candidate canary | Evidence / context / optimization | SQL candidate diagnostics | shadow_only | 0.0 | 0.0 | 0.0 | Kept shadow-only because no alternatives existed. |
| endpoint-family tie-break v2 | Evidence / context / optimization | endpoint routing diagnostics | shadow_only | 0 | unavailable | unavailable | Kept shadow-only because projected positive delta rows = 0. |
| live-mode readiness diagnostics | Evidence / context / optimization | diagnostics | diagnostic_only | unavailable | unavailable | unavailable | Credential visibility is false, so this remains diagnostic. |
| hidden-style eval | Safety / robustness / evaluation | evaluation gate | diagnostic_only | unavailable | unavailable | unavailable | Prevents weakening schema/family routing robustness; current report passes 48/48. |
| leakage / robustness checks | Safety / robustness / evaluation | safety gate | diagnostic_only | unavailable | unavailable | unavailable | Required gate for all accuracy experiments. |
| answer verifier | Safety / robustness / evaluation | answer validation | promoted_default | unavailable | unavailable | unavailable | Core answer safety check. |
| answer reranker | Safety / robustness / evaluation | answer synthesis | promoted_default | unavailable | unavailable | unavailable | Used as packaged answer-selection support. |
| answer claims / slots / intent / diagnostics | Safety / robustness / evaluation | answer analysis | promoted_default | unavailable | unavailable | unavailable | Supports evidence-bound answer generation. |
| package readiness checks | Safety / robustness / evaluation | packaging gate | diagnostic_only | unavailable | unavailable | unavailable | Final readiness gate remains passing in winner report. |
| secret scan | Safety / robustness / evaluation | packaging gate | diagnostic_only | unavailable | unavailable | unavailable | Required readiness gate. |
| trajectory checkpoints | Safety / robustness / evaluation | observability | promoted_default | unavailable | unavailable | unavailable | Core observability surface used by these visualizations. |
| OpenRouter LLM rewrite search | Safety / robustness / evaluation | isolated candidate search | shadow_only | unavailable | unavailable | unavailable | Kept shadow-only; safe rows = 0. |
| supportable dry-run rewrite validation | Safety / robustness / evaluation | answer candidate safety | shadow_only | -0.0127 | unavailable | unavailable | Safe rows feed isolated trials only. |
| autonomous packaged trials | Safety / robustness / evaluation | isolated trial | shadow_only | 0.0067 | 0.0067 | -3.6571 | Best isolated score improved but target 0.75 was not reached. |

## Evidence / context / optimization
### official-token reduction

| Field | Value |
| --- | --- |
| Purpose | Reduces context/token cost while preserving packaged behavior. |
| Pipeline stage | context optimization |
| Input | metadata and prompt context |
| Output | reduced prompt/context tokens |
| Decision boundary | Promoted default and kept enabled. |
| State | promoted_default |
| Files/modules | dashagent/token_reduction_policy.py, dashagent/config.py |
| Checkpoints | checkpoint_official_token_reduction |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Hidden-style remains 48/48. |
| Safety notes | Promoted default and kept enabled. |
| Why promoted / not promoted | Promoted because strict score tied/improved safely with large token reduction. |
| Source reports | outputs/official_token_reduction_promotion_report.json#summary |

### local knowledge index

| Field | Value |
| --- | --- |
| Purpose | Builds Parquet-derived evidence objects for grounding. |
| Pipeline stage | evidence retrieval |
| Input | DBSnapshot parquet data and schema metadata |
| Output | provenance-safe evidence objects |
| Decision boundary | Evidence objects only; no final-answer cache. |
| State | diagnostic_only |
| Files/modules | dashagent/local_knowledge_index.py |
| Checkpoints | local_index_fact_coverage |
| Strict Δ | 0.0 |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Evidence objects only; no final-answer cache. |
| Why promoted / not promoted | Coverage exists, but score impact is currently 0. |
| Source reports | outputs/local_index_candidate_eval.json#summary |

### cache

| Field | Value |
| --- | --- |
| Purpose | Caches deterministic retrieval/index artifacts. |
| Pipeline stage | retrieval optimization |
| Input | schema and value retrieval keys |
| Output | cache hits or regenerated values |
| Decision boundary | Used only for reproducible local speedups. |
| State | promoted_default |
| Files/modules | dashagent/cache.py |
| Checkpoints | checkpoint_value_entity_retrieval |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Used only for reproducible local speedups. |
| Why promoted / not promoted | Infrastructure; no standalone score claim. |
| Source reports | outputs/candidate_context_report.json#rows |

### evidence_bus

| Field | Value |
| --- | --- |
| Purpose | Carries SQL/API/local evidence into answer synthesis. |
| Pipeline stage | evidence collection |
| Input | tool results and local evidence |
| Output | structured evidence records |
| Decision boundary | Evidence must be recorded before claims can use it. |
| State | promoted_default |
| Files/modules | dashagent/evidence_bus.py |
| Checkpoints | checkpoint_evidence_collection |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Evidence must be recorded before claims can use it. |
| Why promoted / not promoted | Safety layer for supportable answers. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#steps |

### context cards

| Field | Value |
| --- | --- |
| Purpose | Summarizes schema/API/domain hints for compact prompts. |
| Pipeline stage | context selection |
| Input | schema/API metadata and query analysis |
| Output | context cards |
| Decision boundary | Packed into prompt metadata. |
| State | promoted_default |
| Files/modules | dashagent/context_cards.py |
| Checkpoints | checkpoint_context_cards |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Packed into prompt metadata. |
| Why promoted / not promoted | Core compact context mechanism. |
| Source reports | outputs/eval/*/sql_first_api_verify/metadata.json |

### fast paths

| Field | Value |
| --- | --- |
| Purpose | Handles simple deterministic query families with low overhead. |
| Pipeline stage | planning optimization |
| Input | query analysis and schema/API hints |
| Output | fast-path plan or no-op |
| Decision boundary | Validators still gate execution. |
| State | promoted_default |
| Files/modules | dashagent/fast_paths.py |
| Checkpoints | checkpoint_fast_path |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Validators still gate execution. |
| Why promoted / not promoted | Efficiency-oriented infrastructure. |
| Source reports | outputs/eval_results_strict.json#summary |

### call budget

| Field | Value |
| --- | --- |
| Purpose | Limits SQL/API calls for efficiency and trajectory stability. |
| Pipeline stage | planning optimization |
| Input | planned steps and route policy |
| Output | call budget decision |
| Decision boundary | Prevents uncontrolled tool growth. |
| State | promoted_default |
| Files/modules | dashagent/call_budget.py |
| Checkpoints | checkpoint_11_call_budget |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Prevents uncontrolled tool growth. |
| Why promoted / not promoted | Keeps tool calls within packaged efficiency target. |
| Source reports | outputs/eval_results_strict.json#summary.by_strategy.SQL_FIRST_API_VERIFY.avg_tool_call_count |

### evidence policy

| Field | Value |
| --- | --- |
| Purpose | Decides when SQL/API evidence is sufficient or API is required. |
| Pipeline stage | evidence gating |
| Input | route, SQL results, API policy |
| Output | evidence sufficiency decision |
| Decision boundary | Must preserve dry-run honesty. |
| State | promoted_default |
| Files/modules | dashagent/evidence_policy.py |
| Checkpoints | checkpoint_evidence_policy |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Must preserve dry-run honesty. |
| Why promoted / not promoted | Promoted core safety/answerability gate. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoints |

### plan optimizer

| Field | Value |
| --- | --- |
| Purpose | Deduplicates and budgets plan steps before execution. |
| Pipeline stage | planning optimization |
| Input | planned steps |
| Output | optimized plan |
| Decision boundary | Preserves one selected execution plan. |
| State | promoted_default |
| Files/modules | dashagent/plan_optimizer.py |
| Checkpoints | checkpoint_plan_optimizer |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Preserves one selected execution plan. |
| Why promoted / not promoted | Efficiency and safety support for packaged strategy. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#steps |

### compact context experiment

| Field | Value |
| --- | --- |
| Purpose | Tests smaller context windows under strict gates. |
| Pipeline stage | context optimization |
| Input | candidate context |
| Output | compact candidate context |
| Decision boundary | Disabled in packaged system. |
| State | default_off |
| Files/modules | dashagent/schema_context_voter.py |
| Checkpoints | compact_context_shadow_eval |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect; compact context remains disabled. |
| Safety notes | Disabled in packaged system. |
| Why promoted / not promoted | Not promoted under current safety constraints. |
| Source reports | outputs/accuracy_promotion_decision_report.json#compact_context_enabled |

### shadow repair

| Field | Value |
| --- | --- |
| Purpose | Evaluates repaired plans without enabling repair execution. |
| Pipeline stage | repair diagnostics |
| Input | current plan and repaired candidate |
| Output | shadow repair score comparison |
| Decision boundary | Repair execution remains disabled. |
| State | shadow_only |
| Files/modules | dashagent/repair_candidate_selector.py, dashagent/repair_safety_verifier.py |
| Checkpoints | shadow_repair_eval |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Repair execution remains disabled. |
| Why promoted / not promoted | Not promoted because repaired candidates did not pass gates. |
| Source reports | outputs/shadow_repair_eval.json#summary |

### AST-guided SQL candidate canary

| Field | Value |
| --- | --- |
| Purpose | Tests AST quality as a tie-break for SQL candidates. |
| Pipeline stage | SQL candidate diagnostics |
| Input | candidate SQL |
| Output | AST validation/ranking diagnostics |
| Decision boundary | Canary only; no applicable rows changed. |
| State | shadow_only |
| Files/modules | dashagent/sql_ast_candidate_ranker.py |
| Checkpoints | ast_guided_sql_candidate_canary |
| Strict Δ | 0.0 |
| Correctness Δ | 0.0 |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | 0.0 |
| Runtime Δ | 0.0 |
| Tool Δ | 0.0 |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Canary only; no applicable rows changed. |
| Why promoted / not promoted | Kept shadow-only because no alternatives existed. |
| Source reports | outputs/ast_guided_sql_candidate_canary.json#summary |

### endpoint-family tie-break v2

| Field | Value |
| --- | --- |
| Purpose | Shadow-tests deterministic preference for high-confidence ranked endpoint family. |
| Pipeline stage | endpoint routing diagnostics |
| Input | ranked and selected endpoint families |
| Output | divergence report |
| Decision boundary | Shadow-first; no trial-eligible positive rows. |
| State | shadow_only |
| Files/modules | scripts/run_endpoint_family_tiebreak_v2_shadow.py |
| Checkpoints | endpoint_family_tiebreak_v2_shadow |
| Strict Δ | 0 |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Shadow-first; no trial-eligible positive rows. |
| Why promoted / not promoted | Kept shadow-only because projected positive delta rows = 0. |
| Source reports | outputs/endpoint_family_tiebreak_v2_shadow.json#summary |

### live-mode readiness diagnostics

| Field | Value |
| --- | --- |
| Purpose | Reports whether real Adobe credentials and live API payload readiness exist. |
| Pipeline stage | diagnostics |
| Input | environment credential visibility and trajectories |
| Output | live readiness report |
| Decision boundary | Diagnostic only unless credentials are present. |
| State | diagnostic_only |
| Files/modules | scripts/run_live_mode_readiness_check.py |
| Checkpoints | live_mode_readiness_report |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Does not change dry-run behavior. |
| Safety notes | Diagnostic only unless credentials are present. |
| Why promoted / not promoted | Credential visibility is false, so this remains diagnostic. |
| Source reports | outputs/live_mode_readiness_report.json#summary |

## Planning / execution
### SQL_FIRST_API_VERIFY

| Field | Value |
| --- | --- |
| Purpose | Grounds with local SQL first, then verifies with API where needed. |
| Pipeline stage | strategy |
| Input | metadata/context and route policy |
| Output | SQL/API execution plan |
| Decision boundary | Preferred packaged strategy. |
| State | promoted_default |
| Files/modules | dashagent/executor.py, dashagent/planner.py |
| Checkpoints | checkpoint_planning, checkpoint_execution |
| Strict Δ | 0.0 |
| Correctness Δ | 0.0 |
| Answer Δ | 0.3337 |
| SQL Δ | 0.9333 |
| API Δ | 0.9791 |
| Token Δ | 797.9429 |
| Runtime Δ | 1.3502 |
| Tool Δ | 1.4571 |
| Hidden-style impact | Hidden-style 48/48 in current report. |
| Safety notes | Preferred packaged strategy. |
| Why promoted / not promoted | Best current strict score and correctness among packaged strategies. |
| Source reports | outputs/eval_results_strict.json#summary.by_strategy.SQL_FIRST_API_VERIFY |

### SQL templates

| Field | Value |
| --- | --- |
| Purpose | Generate validated SQL for recurring local-data query families. |
| Pipeline stage | SQL planning |
| Input | schema metadata and query analysis |
| Output | read-only SQL |
| Decision boundary | Only validated read-only SQL may execute. |
| State | promoted_default |
| Files/modules | dashagent/sql_templates.py, dashagent/validators.py |
| Checkpoints | checkpoint_sql_template, checkpoint_sql_ast_validation |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Only validated read-only SQL may execute. |
| Why promoted / not promoted | Reusable templates are part of current SQL score. |
| Source reports | outputs/eval_results_strict.json#summary.by_strategy.SQL_FIRST_API_VERIFY.avg_sql_score |

### API templates

| Field | Value |
| --- | --- |
| Purpose | Generate endpoint-catalog-valid API calls. |
| Pipeline stage | API planning |
| Input | endpoint catalog, route policy, grounded IDs |
| Output | method/path/params |
| Decision boundary | Catalog validation must pass; dry-run is honest when credentials are absent. |
| State | promoted_default |
| Files/modules | dashagent/api_templates.py, dashagent/endpoint_catalog.py |
| Checkpoints | checkpoint_api_template, checkpoint_api_validation |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Catalog validation must pass; dry-run is honest when credentials are absent. |
| Why promoted / not promoted | Reusable endpoint templates drive current API score. |
| Source reports | outputs/eval_results_strict.json#summary.by_strategy.SQL_FIRST_API_VERIFY.avg_api_score |

### planner

| Field | Value |
| --- | --- |
| Purpose | Builds constrained SQL/API steps from route and context. |
| Pipeline stage | planning |
| Input | route, metadata, templates |
| Output | candidate plan |
| Decision boundary | Plan optimizer and validators gate execution. |
| State | promoted_default |
| Files/modules | dashagent/planner.py, dashagent/executor.py |
| Checkpoints | checkpoint_planning |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Plan optimizer and validators gate execution. |
| Why promoted / not promoted | Core packaged execution path. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#steps |

### executor

| Field | Value |
| --- | --- |
| Purpose | Runs validated SQL/API calls and records trajectory evidence. |
| Pipeline stage | execution |
| Input | selected plan |
| Output | tool results, evidence, trajectory |
| Decision boundary | Executes one selected plan; no multi-plan runtime execution. |
| State | promoted_default |
| Files/modules | dashagent/executor.py |
| Checkpoints | checkpoint_execution, checkpoint_answer_synthesis |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Executes one selected plan; no multi-plan runtime execution. |
| Why promoted / not promoted | Required packaged runtime component. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json |

### endpoint catalog

| Field | Value |
| --- | --- |
| Purpose | Defines allowed Adobe API endpoints and validation metadata. |
| Pipeline stage | API validation |
| Input | endpoint templates and planned API calls |
| Output | catalog validation result |
| Decision boundary | Unknown endpoints are rejected. |
| State | promoted_default |
| Files/modules | dashagent/endpoint_catalog.py |
| Checkpoints | checkpoint_api_validation |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Unknown endpoints are rejected. |
| Why promoted / not promoted | Safety boundary for API calls. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#api validation |

### endpoint family ranker

| Field | Value |
| --- | --- |
| Purpose | Ranks endpoint families from reusable intent features. |
| Pipeline stage | endpoint ranking |
| Input | query tokens and endpoint metadata |
| Output | ranked endpoint families |
| Decision boundary | Packaged ranking signal; v2 tie-break remains shadow-only. |
| State | promoted_default |
| Files/modules | dashagent/endpoint_family_ranker.py |
| Checkpoints | checkpoint_endpoint_family_ranking |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Packaged ranking signal; v2 tie-break remains shadow-only. |
| Why promoted / not promoted | Ranking is used; broader tie-break changes were not promoted. |
| Source reports | outputs/endpoint_family_tiebreak_v2_shadow.json#summary |

### endpoint-schema rule candidates

| Field | Value |
| --- | --- |
| Purpose | Shadow-tests reusable endpoint/schema routing rules. |
| Pipeline stage | endpoint/schema routing |
| Input | query vocabulary, catalog metadata, path shapes |
| Output | candidate reranking diagnostics |
| Decision boundary | Canary only; no measurable improvement in current report. |
| State | shadow_only |
| Files/modules | dashagent/endpoint_schema_rule_candidates.py |
| Checkpoints | checkpoint_endpoint_schema_rule_candidates |
| Strict Δ | 0.0 |
| Correctness Δ | 0.0 |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | 0.0 |
| Runtime Δ | 0.0 |
| Tool Δ | 0.0 |
| Hidden-style impact | Hidden-style gate passed in canary. |
| Safety notes | Canary only; no measurable improvement in current report. |
| Why promoted / not promoted | Kept shadow-only because measurable improvement was false. |
| Source reports | outputs/endpoint_schema_rule_canary.json#summary |

### candidate generation

| Field | Value |
| --- | --- |
| Purpose | Generates deterministic alternative plans for isolated search. |
| Pipeline stage | candidate search |
| Input | query, schema metadata, endpoint catalog |
| Output | candidate SQL/API/answer plans |
| Decision boundary | Isolated search only; packaged path unchanged. |
| State | shadow_only |
| Files/modules | dashagent/targeted_candidate_generator.py |
| Checkpoints | candidate_search |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Isolated search only; packaged path unchanged. |
| Why promoted / not promoted | No broad runtime promotion; used for diagnostics/trials. |
| Source reports | outputs/execution_candidate_search.json#summary |

### execution-based candidate selector

| Field | Value |
| --- | --- |
| Purpose | Scores isolated candidates and selects only safe improvements. |
| Pipeline stage | candidate search |
| Input | candidate plans and strict offline scores |
| Output | safe candidate bundle |
| Decision boundary | Never changes packaged output directly. |
| State | shadow_only |
| Files/modules | dashagent/execution_based_candidate_selector.py |
| Checkpoints | candidate_search |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Never changes packaged output directly. |
| Why promoted / not promoted | Kept isolated unless trial gates pass. |
| Source reports | outputs/execution_candidate_search.json#summary |

### answer-shape v2

| Field | Value |
| --- | --- |
| Purpose | Tests concise answer-shape rewrites with row-level A/B diagnostics. |
| Pipeline stage | answer synthesis |
| Input | baseline answer and evidence |
| Output | candidate answer |
| Decision boundary | Default-off; selected rows only in isolated trial. |
| State | default_off |
| Files/modules | scripts/run_answer_shape_v2_ab_eval.py |
| Checkpoints | answer_shape_v2_ab_eval |
| Strict Δ | 0.0006 |
| Correctness Δ | 0.0006 |
| Answer Δ | -0.1162 |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Hidden-style gate passed. |
| Safety notes | Default-off; selected rows only in isolated trial. |
| Why promoted / not promoted | Not a packaged default; isolated trial was below 0.75 target. |
| Source reports | outputs/answer_shape_v2_ab_eval.json#summary |

### supportable answer rewriter

| Field | Value |
| --- | --- |
| Purpose | Creates evidence-cited dry-run-safe answer rewrites. |
| Pipeline stage | answer synthesis |
| Input | recorded evidence, endpoint params, dry-run labels |
| Output | supportable answer candidates |
| Decision boundary | Answer-only; SQL/API hashes and tools must stay unchanged. |
| State | shadow_only |
| Files/modules | dashagent/supportable_answer_rewriter.py |
| Checkpoints | supportable_answer_rewrite_eval |
| Strict Δ | -0.0069 |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Answer-only; SQL/API hashes and tools must stay unchanged. |
| Why promoted / not promoted | Safe rows feed isolated trials; not final promoted behavior. |
| Source reports | outputs/supportable_answer_rewrite_eval.json#summary |

### SQL-only API-skip guard

| Field | Value |
| --- | --- |
| Purpose | Conservatively skips API only when SQL fully answers and API score is not needed. |
| Pipeline stage | pre-execution guard |
| Input | route policy, SQL evidence, strict diagnostics |
| Output | API_SKIP decision metadata |
| Decision boundary | Default-off. |
| State | default_off |
| Files/modules | dashagent/sql_only_api_skip_guard.py |
| Checkpoints | sql_only_api_skip_guard |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Default-off. |
| Why promoted / not promoted | Not promoted; conservative guard available behind flag only. |
| Source reports | outputs/live_mode_readiness_report.json#summary.sql_only_skip_guard_rows |

## Query understanding / routing
### query_normalizer

| Field | Value |
| --- | --- |
| Purpose | Canonicalizes user text before routing and retrieval. |
| Pipeline stage | query understanding |
| Input | raw query |
| Output | normalized query and rewrite hints |
| Decision boundary | Always runs in packaged path. |
| State | promoted_default |
| Files/modules | dashagent/query_normalizer.py |
| Checkpoints | checkpoint_02_query_normalization |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Always runs in packaged path. |
| Why promoted / not promoted | Deterministic preprocessing; retained as core routing support. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoints |

### query_tokens

| Field | Value |
| --- | --- |
| Purpose | Extracts tokens, quoted entities, and intent words for downstream ranking. |
| Pipeline stage | query understanding |
| Input | normalized query |
| Output | tokens and quoted entities |
| Decision boundary | Always runs in packaged path. |
| State | promoted_default |
| Files/modules | dashagent/query_tokens.py |
| Checkpoints | checkpoint_03_query_tokens |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Always runs in packaged path. |
| Why promoted / not promoted | Low-cost deterministic signal used by ranking and templates. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoints |

### relevance_scorer

| Field | Value |
| --- | --- |
| Purpose | Ranks schema/API candidates using query-token overlap and metadata relevance. |
| Pipeline stage | candidate ranking |
| Input | tokens, schema metadata, endpoint metadata |
| Output | candidate relevance scores |
| Decision boundary | Used before metadata selection; no isolated score delta available. |
| State | promoted_default |
| Files/modules | dashagent/relevance_scorer.py, dashagent/candidate_ranker.py |
| Checkpoints | checkpoint_candidate_context, checkpoint_06_candidate_ranking |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Used before metadata selection; no isolated score delta available. |
| Why promoted / not promoted | Core ranking signal; effects are embedded in current packaged metrics. |
| Source reports | outputs/eval_results_strict.json#summary.by_strategy.SQL_FIRST_API_VERIFY |

### plan_ensemble

| Field | Value |
| --- | --- |
| Purpose | Deduplicates and selects a single plan from deterministic planning candidates. |
| Pipeline stage | planning |
| Input | candidate plans |
| Output | one selected plan |
| Decision boundary | Execute exactly one selected plan per query. |
| State | promoted_default |
| Files/modules | dashagent/plan_ensemble.py |
| Checkpoints | checkpoint_plan_ensemble |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Execute exactly one selected plan per query. |
| Why promoted / not promoted | Preserves deterministic single-plan execution. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#steps |

### metadata_selector

| Field | Value |
| --- | --- |
| Purpose | Builds compact per-query metadata/context for planning. |
| Pipeline stage | context selection |
| Input | candidate tables, APIs, context cards |
| Output | metadata.json and filled system prompt context |
| Decision boundary | Always active in packaged SQL_FIRST_API_VERIFY path. |
| State | promoted_default |
| Files/modules | dashagent/metadata_selector.py |
| Checkpoints | checkpoint_metadata_selection |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Always active in packaged SQL_FIRST_API_VERIFY path. |
| Why promoted / not promoted | Needed to keep prompt context compact and deterministic. |
| Source reports | outputs/eval/*/sql_first_api_verify/metadata.json |

### query_analysis

| Field | Value |
| --- | --- |
| Purpose | Classifies route type, answer shape, and domain family. |
| Pipeline stage | query analysis |
| Input | query tokens and schema/API hints |
| Output | route_type, domain_type, answer intent |
| Decision boundary | Always active before planning. |
| State | promoted_default |
| Files/modules | dashagent/query_analysis.py |
| Checkpoints | checkpoint_query_analysis |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Hidden-style 48/48 in current report. |
| Safety notes | Always active before planning. |
| Why promoted / not promoted | Core deterministic intent layer. |
| Source reports | outputs/hidden_style_eval.json#summary |

### prompt_router

| Field | Value |
| --- | --- |
| Purpose | Fast prompt-level route gate for SQL/API need and risk. |
| Pipeline stage | routing |
| Input | raw query |
| Output | route policy and requires_api decision |
| Decision boundary | Always runs; conservative API decisions remain guarded. |
| State | promoted_default |
| Files/modules | dashagent/prompt_router.py, dashagent/router.py |
| Checkpoints | checkpoint_00_prompt_router |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Hidden-style 48/48 in current report. |
| Safety notes | Always runs; conservative API decisions remain guarded. |
| Why promoted / not promoted | Promoted as routing safety layer. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoint_00_prompt_router |

## Safety / robustness / evaluation
### hidden-style eval

| Field | Value |
| --- | --- |
| Purpose | Checks paraphrase/hidden-style routing robustness. |
| Pipeline stage | evaluation gate |
| Input | hidden-style cases |
| Output | pass/fail and stability metrics |
| Decision boundary | Report gate only; runtime behavior unchanged. |
| State | diagnostic_only |
| Files/modules | scripts/run_hidden_style_eval.py |
| Checkpoints | hidden_style_eval |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | Passed 48/48; family stability 1.0; schema stability 1.0. |
| Safety notes | Report gate only; runtime behavior unchanged. |
| Why promoted / not promoted | Prevents weakening schema/family routing robustness; current report passes 48/48. |
| Source reports | outputs/hidden_style_eval.json#summary |

### leakage / robustness checks

| Field | Value |
| --- | --- |
| Purpose | Rejects query-id, exact-query, gold-path, or answer-memorization behavior. |
| Pipeline stage | safety gate |
| Input | candidate triggers and reports |
| Output | leakage pass/fail flags |
| Decision boundary | Applied to canaries/trials. |
| State | diagnostic_only |
| Files/modules | tests/test_score075_robustness_leakage.py |
| Checkpoints | leakage_check |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No leakage flags in current canary summaries. |
| Safety notes | Applied to canaries/trials. |
| Why promoted / not promoted | Required gate for all accuracy experiments. |
| Source reports | outputs/endpoint_schema_rule_canary.json#summary.leakage_check_passed |

### answer verifier

| Field | Value |
| --- | --- |
| Purpose | Checks final answer support and consistency. |
| Pipeline stage | answer validation |
| Input | final answer and evidence |
| Output | verification result |
| Decision boundary | Runs before final answer logging. |
| State | promoted_default |
| Files/modules | dashagent/answer_verifier.py |
| Checkpoints | checkpoint_16_answer_verification |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Runs before final answer logging. |
| Why promoted / not promoted | Core answer safety check. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoint_16_answer_verification |

### answer reranker

| Field | Value |
| --- | --- |
| Purpose | Ranks candidate answer phrasings when alternatives are available. |
| Pipeline stage | answer synthesis |
| Input | candidate answers |
| Output | selected answer |
| Decision boundary | Must stay evidence-supported. |
| State | promoted_default |
| Files/modules | dashagent/answer_reranker.py |
| Checkpoints | answer_reranker |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Must stay evidence-supported. |
| Why promoted / not promoted | Used as packaged answer-selection support. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#answer checkpoints |

### answer claims / slots / intent / diagnostics

| Field | Value |
| --- | --- |
| Purpose | Extracts answer shape, requested facts, and diagnostic slots. |
| Pipeline stage | answer analysis |
| Input | query and answer evidence |
| Output | answer intent/slots/claims |
| Decision boundary | No unsupported claim should become a final fact. |
| State | promoted_default |
| Files/modules | dashagent/answer_claims.py, dashagent/answer_slots.py, dashagent/answer_intent.py, dashagent/answer_diagnostics.py |
| Checkpoints | answer_diagnostics |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | No unsupported claim should become a final fact. |
| Why promoted / not promoted | Supports evidence-bound answer generation. |
| Source reports | outputs/score_component_error_report.json#summary |

### package readiness checks

| Field | Value |
| --- | --- |
| Purpose | Verifies packaged outputs and final submission readiness. |
| Pipeline stage | packaging gate |
| Input | final submission artifacts |
| Output | readiness result |
| Decision boundary | Does not change runtime behavior. |
| State | diagnostic_only |
| Files/modules | scripts/check_submission_ready.py |
| Checkpoints | check_submission_ready |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style effect. |
| Safety notes | Does not change runtime behavior. |
| Why promoted / not promoted | Final readiness gate remains passing in winner report. |
| Source reports | outputs/winner_readiness_report.json#final_recommendation |

### secret scan

| Field | Value |
| --- | --- |
| Purpose | Prevents credential leakage in packaged outputs/reports. |
| Pipeline stage | packaging gate |
| Input | repo outputs and final submission |
| Output | no_secret_scan result |
| Decision boundary | Does not change runtime behavior. |
| State | diagnostic_only |
| Files/modules | scripts/check_submission_ready.py |
| Checkpoints | no_secret_scan |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style effect. |
| Safety notes | Does not change runtime behavior. |
| Why promoted / not promoted | Required readiness gate. |
| Source reports | outputs/winner_readiness_report.json#packaged |

### trajectory checkpoints

| Field | Value |
| --- | --- |
| Purpose | Records execution checkpoints for explainability and auditability. |
| Pipeline stage | observability |
| Input | pipeline stage outputs |
| Output | trajectory checkpoint list |
| Decision boundary | Always written for packaged query outputs. |
| State | promoted_default |
| Files/modules | dashagent/trajectory.py, dashagent/span_exporter.py |
| Checkpoints | checkpoints |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No hidden-style regression reported. |
| Safety notes | Always written for packaged query outputs. |
| Why promoted / not promoted | Core observability surface used by these visualizations. |
| Source reports | outputs/eval/*/sql_first_api_verify/trajectory.json#checkpoints |

### OpenRouter LLM rewrite search

| Field | Value |
| --- | --- |
| Purpose | Uses LLM proposals only for evidence-cited answer rewrites. |
| Pipeline stage | isolated candidate search |
| Input | baseline answer and local evidence registry |
| Output | candidate rewrites with claim citations |
| Decision boundary | LLM output is proposal-only and must pass local validators. |
| State | shadow_only |
| Files/modules | dashagent/llm_candidate_generator.py, scripts/run_llm_answer_rewrite_search.py |
| Checkpoints | llm_answer_rewrite_search |
| Strict Δ | unavailable |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | LLM output is proposal-only and must pass local validators. |
| Why promoted / not promoted | Kept shadow-only; safe rows = 0. |
| Source reports | outputs/llm_answer_rewrite_search.json#summary |

### supportable dry-run rewrite validation

| Field | Value |
| --- | --- |
| Purpose | Validates claim citations, dry-run unavailable wording, and SQL/API hash invariance. |
| Pipeline stage | answer candidate safety |
| Input | candidate rewrites |
| Output | safe/unsafe rewrite labels |
| Decision boundary | Rejects fabricated payloads and unsupported claims. |
| State | shadow_only |
| Files/modules | dashagent/supportable_answer_rewriter.py |
| Checkpoints | supportable_answer_rewrite_eval |
| Strict Δ | -0.0127 |
| Correctness Δ | unavailable |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | unavailable |
| Runtime Δ | unavailable |
| Tool Δ | unavailable |
| Hidden-style impact | No packaged hidden-style effect. |
| Safety notes | Rejects fabricated payloads and unsupported claims. |
| Why promoted / not promoted | Safe rows feed isolated trials only. |
| Source reports | outputs/evidence_answer_candidate_eval.json#summary |

### autonomous packaged trials

| Field | Value |
| --- | --- |
| Purpose | Runs isolated packaged-style trials over safe candidate bundles. |
| Pipeline stage | isolated trial |
| Input | safe candidate bundle |
| Output | best isolated score and gate results |
| Decision boundary | Does not overwrite official packaged outputs. |
| State | shadow_only |
| Files/modules | scripts/run_autonomous_packaged_trial.py |
| Checkpoints | autonomous_packaged_trial |
| Strict Δ | 0.0067 |
| Correctness Δ | 0.0067 |
| Answer Δ | unavailable |
| SQL Δ | unavailable |
| API Δ | unavailable |
| Token Δ | -3.6571 |
| Runtime Δ | -0.001 |
| Tool Δ | 0.0 |
| Hidden-style impact | Hidden-style gate passed in trial summary. |
| Safety notes | Does not overwrite official packaged outputs. |
| Why promoted / not promoted | Best isolated score improved but target 0.75 was not reached. |
| Source reports | outputs/autonomous_packaged_trial.json#summary |
