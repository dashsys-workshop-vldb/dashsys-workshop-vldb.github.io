# Final Research-Inspired Improvement Report

Status: **no measured strict-score improvement**.

## Metrics

| Metric | Baseline | Current | Delta |
| --- | ---: | ---: | ---: |
| strict_final_score | 0.649 | 0.6486 | -0.0004 |
| strict_correctness | 0.6743 | 0.6743 | 0.0 |
| estimated_tokens | 851.7714 | 899.2286 | 47.4572 |
| runtime | 0.0102 | 0.0111 | 0.0009 |
| tool_calls | 1.4571 | 1.4571 | 0.0 |

## Gate Results

- Packaged preferred strategy: `SQL_FIRST_API_VERIFY`
- Strict score regression gate OK: True
- Estimated-token overhead: 5.57% (gate OK: True)
- Runtime overhead: 8.82% (gate OK: True)
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
- Risk-controller estimated runtime savings total ms: 175.0 (measured efficiency improvement claimed: False)
- Packaged execution changed: False
- Measured accuracy improvement claimed: False
- Measured efficiency improvement claimed: False
- No behavior-changing flags were enabled in this pass.
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
| `ENABLE_OFFICIAL_TOKEN_REDUCTION` | False |

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

## Diagnostic Candidate Risk Clusters

| Cluster | Before | After | Delta | Improved? | Diagnostic only | Behavior changing? |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `batch_endpoint_confusion` | 8 | 5 | -3 | True | True | False |
| `broad_domain_api_confusion` | 4 | 1 | -3 | True | True | False |
| `low_confidence` | 14 | 2 | -12 | True | True | False |
| `missing_gold_api_in_top_k` | 15 | 7 | -8 | True | True | False |
| `missing_gold_table_in_top_k` | 4 | 2 | -2 | True | True | False |
| `schema_vs_dataset_confusion` | 4 | 0 | -4 | True | True | False |
| `tag_api_confusion` | 4 | 1 | -3 | True | True | False |
| `zero_score_margin` | 32 | 6 | -26 | True | True | False |

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
- SQLGlot AST diagnostics are reported safely; ParseError values are captured as diagnostics rather than crashing the pipeline.
- No live API evidence is fabricated; Adobe API remains dry-run without credentials.
- Gated SQL candidates validate multiple candidates but execute one selected SQL in packaged SQL_FIRST mode.
- Inactive techniques appear compactly in visualization status tables, not as empty checkpoints.
- Behavior-changing repair execution is feature-flagged off by default; strict score and efficiency gates decide whether it can ever be enabled.
- No behavior-changing flags were enabled in this pass.
