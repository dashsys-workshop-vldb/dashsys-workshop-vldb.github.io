# DASHSys Progress Deck Diagrams

These diagrams are generated source assets for the DASHSys Systems Track progress deck.

## Tooling

- Diagram source: Mermaid flowchart files (`.mmd`) are generated as readable source companions.
- Rendered export: Graphviz DOT (`.dot`) is the layout source of truth for `.svg` and high-resolution `.png`.
- The DOT diagrams use object boxes, decision diamonds, score/table-like nodes, state transitions, and labeled payload arrows so the deck avoids fragile PowerPoint-native diagram layout.

## Regeneration

```bash
node scripts/generate_dashsys_diagrams.mjs
node scripts/create_dashsys_progress_deck.mjs
```

The PowerPoint generator inserts the exported `.png` files instead of manually recreating diagrams with many PowerPoint text boxes.

## Slide Mapping

| PPT slide | Diagram | Mermaid source | PNG export |
|---:|---|---|---|
| 6 | Schema-guided planning: SQL/API templates | `diagrams/technique_01_sql_api_templates.mmd` | `diagrams/technique_01_sql_api_templates.png` |
| 7 | Error-driven optimization: failure_analysis | `diagrams/technique_02_failure_analysis.mmd` | `diagrams/technique_02_failure_analysis.png` |
| 8 | Structured generation: answer_templates | `diagrams/technique_03_answer_templates.mmd` | `diagrams/technique_03_answer_templates.png` |
| 9 | Conditional execution: evidence_policy | `diagrams/technique_04_evidence_policy.mmd` | `diagrams/technique_04_evidence_policy.png` |
| 10 | Resource scheduling: call_budget | `diagrams/technique_05_call_budget.mmd` | `diagrams/technique_05_call_budget.png` |
| 11 | Operand forwarding: EvidenceBus | `diagrams/technique_06_evidence_bus.mmd` | `diagrams/technique_06_evidence_bus.png` |
| 12 | Shared decode: QueryAnalysis | `diagrams/technique_07_query_analysis.mmd` | `diagrams/technique_07_query_analysis.png` |
| 13 | Lookup-path prediction: LookupPathPredictor | `diagrams/technique_08_lookup_path_predictor.mmd` | `diagrams/technique_08_lookup_path_predictor.png` |
| 14 | Compiler optimization: PlanOptimizer | `diagrams/technique_09_plan_optimizer.mmd` | `diagrams/technique_09_plan_optimizer.png` |
| 15 | Multi-level caching: cache.py | `diagrams/technique_10_cache_hierarchy.mmd` | `diagrams/technique_10_cache_hierarchy.png` |
| 16 | Context packing: context_cards | `diagrams/technique_11_context_cards.mmd` | `diagrams/technique_11_context_cards.png` |
| 17 | Data cleaning: query_normalizer | `diagrams/technique_12_query_normalizer.mmd` | `diagrams/technique_12_query_normalizer.png` |
| 18 | Tokenization and entity extraction: query_tokens | `diagrams/technique_13_query_tokens.mmd` | `diagrams/technique_13_query_tokens.png` |
| 19 | Attention-style selection: relevance_scorer | `diagrams/technique_14_relevance_scorer.mmd` | `diagrams/technique_14_relevance_scorer.png` |
| 20 | Ensemble selection: plan_ensemble | `diagrams/technique_15_plan_ensemble.mmd` | `diagrams/technique_15_plan_ensemble.png` |
| 21 | Evidence slot extraction: answer_slots | `diagrams/technique_16_answer_slots.mmd` | `diagrams/technique_16_answer_slots.png` |
| 22 | Intent-aware response shaping: answer_intent | `diagrams/technique_17_answer_intent.mmd` | `diagrams/technique_17_answer_intent.png` |
| 23 | Claim decomposition: answer_claims | `diagrams/technique_18_answer_claims.mmd` | `diagrams/technique_18_answer_claims.png` |
| 24 | Groundedness checking: answer_verifier | `diagrams/technique_19_answer_verifier.mmd` | `diagrams/technique_19_answer_verifier.png` |
| 25 | Deterministic reranking: answer_reranker | `diagrams/technique_20_answer_reranker.mmd` | `diagrams/technique_20_answer_reranker.png` |
| 26 | Error observability: answer_diagnostics | `diagrams/technique_21_answer_diagnostics.mmd` | `diagrams/technique_21_answer_diagnostics.png` |
| 27 | Whole Project Workflow: Planning Dataflow | `diagrams/whole_project_planning_dataflow.mmd` | `diagrams/whole_project_planning_dataflow.png` |
| 28 | Whole Project Workflow: Evidence and Answer Dataflow | `diagrams/whole_project_evidence_answer_dataflow.mmd` | `diagrams/whole_project_evidence_answer_dataflow.png` |
| 29 | Concrete Birthday Message Example | `diagrams/concrete_birthday_message.mmd` | `diagrams/concrete_birthday_message.png` |
| 30 | Memory and Cache Hierarchy | `diagrams/memory_cache_hierarchy.mmd` | `diagrams/memory_cache_hierarchy.png` |

The full one-file whole-project diagram is also generated for source completeness:
`diagrams/whole_project_workflow.mmd`, `diagrams/whole_project_workflow.dot`, `diagrams/whole_project_workflow.svg`, and `diagrams/whole_project_workflow.png`.

## Style

- Purple: planning/control
- Blue: SQL/local database
- Orange: API/live or dry-run
- Green: validation/verification
- Teal: evidence
- Gray: artifacts/logging
