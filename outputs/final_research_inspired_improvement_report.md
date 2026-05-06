# Final Research-Inspired Improvement Report

Status: **no measured strict-score improvement**.

## Metrics

| Metric | Baseline | Current | Delta |
| --- | ---: | ---: | ---: |
| strict_final_score | 0.649 | 0.6486 | -0.0004 |
| strict_correctness | 0.6743 | 0.6743 | 0.0 |
| estimated_tokens | 851.7714 | 899.2286 | 47.4572 |
| runtime | 0.0102 | 0.0115 | 0.0013 |
| tool_calls | 1.4571 | 1.4571 | 0.0 |

## Gate Results

- Packaged preferred strategy: `SQL_FIRST_API_VERIFY`
- Strict score regression gate OK: True
- Estimated-token overhead: 5.57% (gate OK: True)
- Runtime overhead: 12.75% (gate OK: True)
- Tool-call delta: 0.0 (gate OK: True)
- Value retrieval budget: 250 ms (budget OK: True)
- Value retrieval cache key algorithm: `sha256` (reproducible: True)
- Candidate risk clusters reported: 8
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

## Diagnostic Candidate Risk Clusters

| Cluster | Count | Diagnostic only | Behavior changing? |
| --- | ---: | --- | --- |
| `batch_endpoint_confusion` | 11 | True | False |
| `broad_domain_api_confusion` | 11 | True | False |
| `low_confidence` | 14 | True | False |
| `missing_gold_api_in_top_k` | 15 | True | False |
| `missing_gold_table_in_top_k` | 2 | True | False |
| `schema_vs_dataset_confusion` | 8 | True | False |
| `tag_api_confusion` | 4 | True | False |
| `zero_score_margin` | 32 | True | False |

## Research Safety Audit

- public_query_overlap: False
- gold_sql_overlap: False
- public_answer_overlap: False
- public_entity_overlap: False
- used_gold_patterns: False

## Notes

- Value retrieval cache filenames use stable SHA-256 keys instead of Python process-salted hash().
- Candidate risk clusters are diagnostic-only and do not change candidate ranking or SQL/API generation.
- SQLGlot AST diagnostics are reported safely; ParseError values are captured as diagnostics rather than crashing the pipeline.
- No live API evidence is fabricated; Adobe API remains dry-run without credentials.
- Gated SQL candidates validate multiple candidates but execute one selected SQL in packaged SQL_FIRST mode.
- Inactive techniques appear compactly in visualization status tables, not as empty checkpoints.
- Behavior-changing modules are feature-flagged; strict score and efficiency gates decide whether they remain active.
