# Final Research-Inspired Improvement Report

Status: **strict-score improvement measured**.

## Metrics

| Metric | Baseline | Current | Delta |
| --- | ---: | ---: | ---: |
| strict_final_score | 0.649 | 0.6491 | 0.0001 |
| strict_correctness | 0.6743 | 0.6743 | 0.0 |
| estimated_tokens | 851.7714 | 831.4571 | -20.3143 |
| runtime | 0.0102 | 0.0112 | 0.001 |
| tool_calls | 1.4571 | 1.4571 | 0.0 |

## Gate Results

- Packaged preferred strategy: `SQL_FIRST_API_VERIFY`
- Strict score regression gate OK: True
- Estimated-token overhead: -2.38% (gate OK: True)
- Runtime overhead: 9.80% (gate OK: True)
- Tool-call delta: 0.0 (gate OK: True)
- Value retrieval budget: 250 ms (budget OK: True)
- Value retrieval cache key algorithm: `sha256` (reproducible: True)
- Candidate risk clusters reported: 8
- Retrieval cluster gate: retrieval-cluster improvement measured (passed: True)
- Improved retrieval clusters: zero_score_margin, missing_gold_api_in_top_k, batch_endpoint_confusion, tag_api_confusion, schema_vs_dataset_confusion
- Ranking-only no score claim: True
- Shadow repair eval ran: True
- Shadow repair execution enabled: False
- Shadow repaired better/equal/worse/unsafe: 1/26/8/35
- Risk level distribution: {'high': 28, 'low': 2, 'medium': 5}
- Risk-controller estimated token savings total: 1848.0 (estimated only: True)
- Risk-controller estimated runtime savings total ms: 175.0 (measured efficiency improvement claimed: True)
- Packaged execution changed: True
- Measured accuracy improvement claimed: False
- Measured efficiency improvement claimed: True
- Official-token reduction is the only behavior-changing default enabled; repair execution and compact context remain disabled.
- Schema vote active/agreement/compact-safe: 28/28/28
- Compact-context shadow eval rows: 28 (avg token delta: -1220.7857; measured efficiency improvement claimed: False)
- Compact-context measured eval ran: True (eligible rows: 28; safe rows: 0; avg total token delta: 4.3214; avg context-only token delta: 206.75; avg runtime delta: 0.0016; recommendation: unsafe_do_not_enable)
- Compact-context token classification counts: {'context_and_total_improved': 0, 'context_metric_unavailable_or_unreliable': 0, 'context_only_improved_total_not_improved': 8, 'total_tokens_not_improved': 20}
- Compact-context measured caveat: Schema-vote fallback_context_tokens is a broader-context diagnostic estimate, not necessarily the official current prompt size. The official current path can already be compact-like, so replacing it with schema-vote compact metadata may not save prompt tokens. The official trajectory estimated_tokens metric is computed from query, compact step records, and final answer; it excludes checkpoints and the full filled prompt/context payload. Therefore large replay-estimated context savings can coexist with flat or positive measured total estimated_tokens.
- Compact-context experimental measured efficiency improvement claimed: False
- Compact-context official measured efficiency improvement claimed: False
- Compact-context measured eval changed packaged execution: False
- Compact-context feature flag default: False
- Official token accounting ran: True (expected savings estimate: 5258)
- Official token top contributors: [{'name': 'checkpoint summaries', 'tokens': 185402}, {'name': 'other step/checkpoint payloads', 'tokens': 15071}, {'name': 'API call records', 'tokens': 3914}]
- Official token biggest reducible fields: [{'name': 'other step/checkpoint payloads', 'tokens': 5258}]
- Official token reduction eval ran: True (safe rows: 35; avg token delta: -67.7714; avg score delta: 0.0006; recommendation: safe_for_future_canary)
- Official token reduction changed packaged execution: False
- Official token reduction feature flag default: False
- Official token reduction official efficiency claim: False
- Official token reduction canary ran: True (safe rows: 35; unsafe rows: 0; avg token delta: -67.7714; avg score delta: 0.0006; recommendation: safe_for_packaged_flag_trial)
- Official token reduction canary protected output hashes unchanged: True
- Official token reduction canary changed packaged execution: False
- Official token reduction canary feature flag default: False
- Official token reduction canary official efficiency claim: False
- Official token reduction packaged trial ran: True (safe rows: 35; unsafe rows: 0; avg token delta: -67.7714; avg runtime delta: 0.0005; recommendation: safe_to_make_packaged_default_in_future)
- Official token reduction promotion: attempted=True; kept=True; score delta=0.0005; token delta=-67.7715; final submission diff OK=True; recommendation=promoted_keep_enabled
- Hidden-style eval passed/total: 48/48
- Hidden-style eval failed cases: 0
- Hidden-style family/schema stability: 1.0 / 1.0
- Accuracy decision hidden-style fresh: True
- Endpoint-family failure risky rows: 35
- Endpoint/schema rule candidates: 10 (safe for future canary: 9)
- Endpoint/schema rule canary recommendation: keep_shadow_only (API top-k hit-rate delta: 0.0)
- Endpoint/schema packaged trial recommendation: keep_shadow_only
- Schema/dataset positive repair rows: 1
- SQL AST candidate ranking candidates: 15
- AST-guided SQL canary recommendation: keep_shadow_only
- Retrieval ablation best mode: full_current_retrieval_official_token_reduction
- Repair selector v2 success: False
- Repair selector v3 success: False (strictly better selected: 0)
- Accuracy promotion decision: keep_all_accuracy_changes_shadow_only
- Low-score mining score needed for 0.70: 1.7815
- Score-component report ran: True (API-correct answer-weak rows: 16)
- Evidence-answer candidate eval: safe rows=1; projected score=0.6494
- Answer-shape v2 A/B eval: ran=True; changed rows=35; safe rows=7; projected score=0.6497; recommendation=safe_for_answer_shape_v2_trial
- Unsafe answer analysis: rows=103; positive supportable=18
- Supportable answer rewrite eval: safe rows=4; projected score=0.6552
- LLM answer rewrite search: completed (recommendation: keep_shadow_only; model: openrouter/free; accepted: 0/6)
- LLM baseline framework: generic_sdk_llm_baseline (backend: qwen2.5-32b-instruct; backend_type: openai_sdk; tool calling: True; strict: available; recommendation: keep_shadow_only)
- Endpoint-family tie-break v2 shadow: recommendation=keep_shadow_only; trial eligible rows=0
- Live-mode readiness: diagnostic_only=True; dry-run dependent rows=34
- Local-index fact coverage: requested rows=34; used rows=24
- Execution candidate search safe rows: 5 (best projected score: 0.6556; recommendation: safe_for_targeted_packaged_trial)
- LLM candidate search: skipped_no_llm_key (recommendation: keep_shadow_only)
- Targeted accuracy trial recommendation: keep_shadow_only (score: 0.6491; 0.70 reached: False)
- 0.70 push report: achieved=0.6491; target reached=False; recommendation=submit_current_official_token_reduction_version
- Autonomous packaged trial: score=0.6558; 0.75 reached=False; recommendation=continue_iteration_target_not_reached
- Autonomous 0.75 push report: best=0.6558; 0.75 reached=False; recommendation=continue_iteration_target_not_reached
- score075 integration merged/rejected/pending branches: 0 / 0 / 10
- Redundant file audit ran: True; cleanup applied=False; deleted=0; protected files deleted=False
- Winner readiness next actions: ['Submit with official-token reduction if the promotion report remains kept.', 'Keep repair execution disabled.', 'Keep compact context disabled.', 'Use endpoint/schema rule candidates only as future canary inputs.', 'Keep accuracy changes shadow-only unless the accuracy decision report explicitly recommends promotion.', 'Use the 0.70 push report to decide whether any targeted accuracy change is worth a later explicit promotion.', 'Use the autonomous 0.75 score-push report only after integration has merged and validated worker branches.']
- Risk-efficiency shadow eval rows: 7 (avg token delta: -264.0; avg runtime delta: -0.025; measured efficiency improvement claimed: False)
- Secret scan OK: True
- Visualization artifacts directory: `/Users/tanqinyang/Desktop/dashsys-workshop-vldb/outputs/visualizations`
- Visualization artifacts inside final submission: 0
- Final submission format unchanged: True

## Feature Flags

| Flag | Active |
| --- | --- |
| `ENABLE_SQL_AST_VALIDATION` | True |
| `ENABLE_SCHEMA_LINKING` | True |
| `ENABLE_VALUE_RETRIEVAL` | True |
| `ENABLE_GATED_SQL_CANDIDATES` | True |
| `ENABLE_QUERY_DECOMPOSITION` | True |
| `ENABLE_QUERY_FAMILY_EXAMPLES` | False |
| `ENABLE_RESEARCH_SPAN_EXPORT` | True |
| `ENABLE_HYBRID_CANDIDATE_SCORING` | True |
| `ENABLE_ENDPOINT_FAMILY_RANKING` | True |
| `ENABLE_STRUCTURAL_SCHEMA_PRESERVATION` | True |
| `ENABLE_VALUE_TO_API_RANKING` | True |
| `ENABLE_GATED_RISK_CLUSTER_REPAIR` | True |
| `ENABLE_GATED_RISK_CLUSTER_REPAIR_EXECUTION` | False |
| `ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION` | False |
| `ENABLE_REPAIR_FOR_TAG_API_CONFUSION` | False |
| `ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION` | False |
| `ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN` | False |
| `ENABLE_REPAIR_FOR_MISSING_API_TOPK` | False |
| `ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE` | False |
| `ENABLE_OFFICIAL_TOKEN_REDUCTION` | True |
| `ENABLE_ENDPOINT_SCHEMA_RULE_CANDIDATES` | False |
| `ENABLE_AST_GUIDED_SQL_TIEBREAK` | False |
| `ENABLE_TARGETED_ACCURACY_RULES` | False |
| `ENABLE_ANSWER_SHAPE_V2` | False |
| `ENABLE_SQL_ONLY_API_SKIP_GUARD` | False |
| `ENABLE_ENDPOINT_FAMILY_TIEBREAK_V2` | False |

## Technique Summary

| Technique | Source inspiration | Implemented module | Active in SQL_FIRST? | Active in Raw/GUIDED? | Visualization checkpoint |
| --- | --- | --- | --- | --- | --- |
| SQLGlot AST validation | SQLGlot | `dashagent/sql_ast_tools.py` | True | False | checkpoint_sql_ast_validation |
| Robust schema linking | RSL-SQL | `dashagent/candidate_context_builder.py` | True | False | checkpoint_schema_linking/report metrics |
| Value/entity retrieval | CHESS | `dashagent/value_retrieval.py` | True | False | checkpoint_value_entity_retrieval |
| Query decomposition | DIN-SQL | `dashagent/query_decomposer.py` | True | False | checkpoint_query_decomposition |
| Gated SQL candidates | DIN-SQL/self-correction | `dashagent/gated_sql_candidates.py` | True | False | checkpoint_gated_sql_candidate_selection |
| Query-family examples | DAIL-SQL | `dashagent/query_family_examples.py` | False | False | checkpoint_query_family_examples |
| Span export | OpenAI Agents SDK tracing | `dashagent/span_exporter.py` | True | False | spans.json |
| Hybrid candidate scoring | Blended RAG / rank fusion | `dashagent/candidate_ranker.py` | True | False | checkpoint_hybrid_candidate_scoring/report metrics |
| Endpoint family ranking | domain-aware retrieval | `dashagent/endpoint_family_ranker.py` | True | False | checkpoint_endpoint_family_ranking/report metrics |
| Value-to-API ranking | CHESS value grounding | `dashagent/endpoint_family_ranker.py` | True | False | checkpoint_value_to_api_ranking/report metrics |
| Gated risk-cluster repair | CHASE-SQL-style candidate repair | `dashagent/candidate_context_builder.py` | True | False | checkpoint_gated_risk_cluster_repair/report metrics |
| Risk-based efficiency controller | adaptive retrieval control | `dashagent/risk_efficiency_controller.py` | True | False | checkpoint_risk_efficiency_controller/report metrics |
| Schema context voting | full-vs-compact context voting | `dashagent/schema_context_voter.py` | True | False | checkpoint_schema_context_voting/report metrics |
| Answer-shape v2 A/B eval | evidence-aware answer shaping | `dashagent/answer_shape.py` | False | False | outputs/answer_shape_v2_ab_eval |
| Conservative SQL-only API skip guard | compiler-style no-op elimination | `dashagent/sql_only_api_skip_guard.py` | False | False | api_skip_guard |
| Endpoint-family tie-break v2 shadow | retrieval-to-planner diagnostics | `scripts/run_endpoint_family_tiebreak_v2_shadow.py` | False | False | outputs/endpoint_family_tiebreak_v2_shadow |

## Diagnostic Candidate Risk Clusters

| Cluster | Before | After | Delta | Improved? | Diagnostic only | Behavior changing? |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `batch_endpoint_confusion` | 8 | 5 | -3 | True | True | False |
| `broad_domain_api_confusion` | 4 | 1 | -3 | True | True | False |
| `low_confidence` | 14 | 2 | -12 | True | True | False |
| `missing_gold_api_in_top_k` | 15 | 7 | -8 | True | True | False |
| `missing_gold_table_in_top_k` | 4 | 1 | -3 | True | True | False |
| `schema_vs_dataset_confusion` | 4 | 0 | -4 | True | True | False |
| `tag_api_confusion` | 4 | 1 | -3 | True | True | False |
| `zero_score_margin` | 32 | 8 | -24 | True | True | False |

## Shadow Repair Canary Recommendations

Execution repair remains disabled by default. These recommendations are offline what-if results only.

| Cluster | Rows | Better | Equal | Worse | Avg score delta | Safe to enable? | Recommended flag | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `batch_endpoint_confusion` | 2 | 0 | 2 | 0 | 0.0 | False | `ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION` | keep_disabled |
| `broad_domain_api_confusion` | 1 | 0 | 1 | 0 | 0.0 | False | `None` | keep_disabled |
| `missing_gold_api_in_top_k` | 15 | 0 | 12 | 3 | -0.0286 | False | `ENABLE_REPAIR_FOR_MISSING_API_TOPK` | keep_disabled |
| `schema_vs_dataset_confusion` | 2 | 1 | 1 | 0 | 0.0574 | False | `ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION` | keep_disabled |
| `tag_api_confusion` | 3 | 0 | 3 | 0 | 0.0 | False | `ENABLE_REPAIR_FOR_TAG_API_CONFUSION` | keep_disabled |
| `zero_score_margin` | 6 | 0 | 2 | 4 | -0.1537 | False | `ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN` | keep_disabled |

## Research Safety Audit

- public_query_overlap: False
- gold_sql_overlap: False
- public_answer_overlap: False
- public_entity_overlap: False
- used_gold_patterns: False

## Notes

- Value retrieval cache filenames use stable SHA-256 keys instead of Python process-salted hash().
- Hybrid candidate ranking is report-only for SQL_FIRST_API_VERIFY; it does not change executed SQL/API plans.
- Candidate risk clusters compare old retrieval ordering with ranking/report-only ordering.
- If execution repair remains disabled, ranking changes are not claimed as accuracy improvements.
- Offline shadow repair eval compares candidate-derived repaired plans without changing packaged execution.
- Any repair canary enablement is a recommendation only; canary flags remain disabled by default.
- Risk-based efficiency savings are labeled as estimates; no measured efficiency improvement is claimed because packaged execution did not skip modules.
- Schema context voting compares compact and broader context for high-risk diagnostics only and does not change executed SQL/API plans.
- Compact-context measured eval is experimental only and does not update official packaged scores or submission metrics.
- Official-token reduction eval is experimental only and does not update official packaged scores or submission metrics.
- Official-token reduction canary is isolated and does not update official packaged scores or submission metrics.
- Official-token reduction is promoted as the only behavior-changing default only when the promotion report gates pass.
- Repair selector v2, retrieval ablations, endpoint-family failures, and SQL AST candidate rankings are report-only.
- SQLGlot AST diagnostics are reported safely; ParseError values are captured as diagnostics rather than crashing the pipeline.
- No live API evidence is fabricated; Adobe API remains dry-run without credentials.
- Gated SQL candidates validate multiple candidates but execute one selected SQL in packaged SQL_FIRST mode.
- Inactive techniques appear compactly in visualization status tables, not as empty checkpoints.
- Behavior-changing repair execution is feature-flagged off by default; strict score and efficiency gates decide whether it can ever be enabled.
- Official-token reduction is the only behavior-changing default enabled in this pass; repair execution and compact context remain disabled.
- The 0.70 strict-score push is isolated; targeted accuracy rules remain default-off unless a later explicit promotion passes all gates.
- The autonomous 0.75 score-push is not successful unless strict_final_score >= 0.7500 and every safety gate passes.
- Redundant-file cleanup is allowlist-based and refuses protected source/data/eval/final-submission paths.
