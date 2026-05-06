# DASHSys Prompt-To-Answer Dataflow

## Quality Gate Facts

| Field | Value |
| --- | --- |
| Query ID | `example_000` |
| User query | When was the journey 'Birthday Message' published? |
| Strategy | `RAW_REAL_LLM_TWO_TOOLS_BASELINE` |
| Variant | Raw |
| Final answer preview | The executed query did not find evidence for Birthday Message. This is not a hard proof that it does not exist, because the query/schema choice may be incomplete. |
| Tool call count | 2 |
| Runtime | 10.1537 |
| Estimated tokens | n/a - estimated_tokens missing |
| Checkpoint count | 0 |
| Candidate context mode | candidate |
| Context mode note | recorded in checkpoint/trajectory |

```mermaid
flowchart TD
  subgraph Input
    input_prompt["User Prompt<br/>When was the journey &#x27;Birthday Message&#x27; published?"]
  end
  subgraph Routing
    router["Prompt Router<br/>mode=n/a - no prompt router decision<br/>api=n/a - no API policy recorded"]
    input_prompt -->|route_prompt| router
  end
  subgraph QueryUnderstanding["Query Understanding"]
    normalizer["Query Normalizer<br/>status=not_recorded"]
    tokens["Query Tokens<br/>domains=none&lt;br/&gt;entities=none"]
    router -->|clean + extract| normalizer --> tokens
  end
  subgraph ContextSelection["Context Selection"]
    context["Context Mode<br/>candidate"]
    candidates["Context<br/>tables=none&lt;br/&gt;apis=none"]
    tokens -->|score relevance| context --> candidates
  end
  subgraph Planning
    planner["Planner<br/>RAW_REAL_LLM_TWO_TOOLS_BASELINE"]
    optimizer["Plan Optimizer<br/>selected=n/a - no optimizer selection recorded"]
    candidates -->|metadata + policy| planner --> optimizer
  end
  subgraph SQLPath["SQL Path"]
    sqlgen["SQL Generator<br/>tables=dim_campaign,br_campaign_segment&lt;br/&gt;rows=0"]
    sqlval["SQL Validator<br/>ok"]
    optimizer -->|SQL step if needed| sqlgen --> sqlval
  end
  subgraph APIPath["API Path"]
    apisel["API Selector<br/>endpoint=/ajo/journey"]
    apival["API Validator<br/>ok<br/>dry_run=True"]
    optimizer -->|API policy| apisel --> apival
  end
  subgraph ToolExecution["Tool Execution"]
    tools["Tool Calls<br/>sql=1 api=1<br/>invalid=0"]
    sqlval -->|execute_sql| tools
    apival -->|call_api / dry-run| tools
  end
  subgraph EvidenceBus
    evidence["EvidenceBus<br/>SQL evidence: no&lt;br/&gt;Live API evidence: no&lt;br/&gt;Dry-run API: yes"]
    tools -->|extract facts| evidence
  end
  subgraph AnswerVerification["Answer Verification"]
    verifier["Verifier<br/>status=not_recorded"]
    evidence -->|answer slots + claims| verifier
  end
  subgraph FinalAnswer["Final Answer"]
    answer["Final Answer<br/>The executed query did not find evidence for Birthday Message. This is not a hard proof that it "]
    verifier -->|safe answer| answer
  end
  subgraph Metrics
    metrics["Metrics<br/>tools=2<br/>tokens=n/a - estimated_tokens missing<br/>runtime=10.1537"]
    answer -->|record trajectory| metrics
  end
```

## SQL And API Preview

| Path | Preview | Validation | Result / Status |
| --- | --- | --- | --- |
| SQL | SELECT UPDATEDTIME FROM dim_campaign WHERE CAMPAIGNID IN (SELECT CAMPAIGNID FROM br_campaign_segment WHERE LABELSSEGMENT = 'Birthday Message') | ok | row_count=0; rows={"total_items": 0, "truncated_items": false} |
| API | GET /ajo/journey | ok | dry_run=True; live_api_evidence=False; overall_evidence=False; preview=n/a - no API result preview recorded |

Context mode labels ending in `_inferred` are display-only summaries for the visualization; they are not recorded planner decisions.

## Tool Execution vs Evidence Availability

API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing.

| Metric | Value |
| --- | --- |
| execute_sql calls | 1 |
| call_api calls | 1 |
| valid tool calls | 2 |
| invalid tool calls | 0 |
| endpoint repairs | 0 |
| schema hint injections | 0 |
| SQL evidence available | False |
| live API evidence available | False |
| overall evidence available | False |
| dry-run only | True |
| successful evidence count | 0 |
| zero-row uncertain | True |

## Research Technique Status

| Technique | Source inspiration | Active? | Effect on dataflow | Correctness impact | Efficiency impact | Visualization checkpoint |
| --- | --- | --- | --- | --- | --- | --- |
| SQLGlot AST validation | SQLGlot | False | AST SQL validation and table/column extraction | detects schema/safety mismatches structurally | diagnostic overhead only | checkpoint_sql_ast_validation |
| Robust schema linking | RSL-SQL | False | Bidirectional schema linking and bridge preservation | keeps relevant tables, columns, and bridges visible | diagnostic overhead only | checkpoint_schema_linking |
| Value/entity retrieval | CHESS | False | Entity-value grounding from local DB samples | grounds named entities and IDs before planning | bounded cached retrieval budget | checkpoint_value_entity_retrieval |
| Query decomposition | DIN-SQL | False | Complex-query decomposition into constraints | preserves complex constraints | diagnostic overhead only | checkpoint_query_decomposition |
| Gated SQL candidates | DIN-SQL / self-correction | False | Hard-case candidate validation before one execution | prevents invalid hard-case SQL from being selected | validates only; executes one selected plan | checkpoint_gated_sql_candidate_selection |
| Query-family examples | DAIL-SQL | False | Optional family hints for LLM SQL | makes technique visibility auditable | optional LLM-only token cost | checkpoint_query_family_examples |
| Span export | OpenAI Agents SDK tracing | True | Local span-style checkpoint export | makes technique visibility auditable | diagnostic overhead only | spans.json |
| Hybrid candidate scoring | Blended RAG / rank fusion | True | Report-only candidate separation scoring | makes technique visibility auditable | diagnostic overhead only | checkpoint_hybrid_candidate_scoring |
| Endpoint family ranking | Domain-aware retrieval | True | Report-only endpoint family reranking | makes technique visibility auditable | diagnostic overhead only | checkpoint_endpoint_family_ranking |
| Structural schema preservation | RSL-SQL | True | Report-only bridge/relationship preservation diagnostics | keeps relevant tables, columns, and bridges visible | diagnostic overhead only | checkpoint_structural_schema_preservation |
| Value-to-API ranking | CHESS | False | High-confidence entity matches can boost API-family ranking in reports | grounds named entities and IDs before planning | bounded cached retrieval budget | checkpoint_value_to_api_ranking |
| Gated risk-cluster repair | CHASE-SQL-style repair | True | Diagnostic repaired candidate comparison without execution change | makes technique visibility auditable | diagnostic overhead only | checkpoint_gated_risk_cluster_repair |
| Risk-based efficiency controller | adaptive retrieval control | True | Diagnostic policy that estimates skipped module cost by risk level | makes technique visibility auditable | diagnostic overhead only | checkpoint_risk_efficiency_controller |
| Schema context voting | full-vs-compact context voting | False | High-risk diagnostic comparison of compact and broader context | makes technique visibility auditable | diagnostic overhead only | checkpoint_schema_context_voting |

## Candidate Ranking Diagnostics

| Technique | Active | Output | Correctness role | Efficiency role |
| --- | --- | --- | --- | --- |
| Hybrid Candidate Scoring | True | {"ranking_changed": true, "score_margin": 1.3, "top_candidate_score": 1.8, "top_components": {"alias_score": 1.2, "endpoint_family_score": 0.0, "lexical_score": 0.0, "name": "dim_campaign", "reciprocal_rank_fusion": 0.032787, "score_explanation": "base=2.000; lexical=0.000; alias=1.200; value=0.000; structural=0.000; endpoint_family=0.000", "structural_score": 0.0, "truncated_fields": 1, "value_match_score": 0.0}} | separates candidate context without changing executed plan | report-only scoring; no extra tools |
| Endpoint Family Ranker | True | {"boost_reason": {"items": ["journey_list: journey/campaign vocabulary"], "total_items": 1, "truncated_items": false}, "endpoint_family": "journey_list", "endpoint_family_confidence": 1.0, "ranking_changed": false} | reduces endpoint-family confusion in candidate context | reranks metadata only |
| Structural Schema Preservation | True | {"structural_confidence_delta": 0.1, "structural_reason": "bridge-table heuristic", "structural_tables_added": {"items": ["br_campaign_segment", "hkg_br_segment_target", "hkg_br_source_collection"], "total_items": 7, "truncated_items": true}} | keeps relationship bridge tables visible | adds only compact schema context |
| Value-to-API Ranking | False | {"active": false, "boost_applied": true, "value_match_used_for_api_ranking": false} | uses only high-confidence retrieved values for endpoint family boosts | reuses existing value retrieval diagnostics |
| Gated Risk Cluster Repair | True | {"active": true, "candidate_count": 2, "cost_delta": 0, "diagnostic_only": true, "execution_repair_enabled": false, "expected_correctness_gain": "retrieval-only candidate separation; no accuracy claim without execution change", "hard_case_triggered": true, "rejected_candidate_reason": "lower endpoint-family confidence or lower hybrid score", "truncated_fields": 2} | compares a repaired candidate without executing losing plans | diagnostic-only; zero tool-call delta |

## Shadow Repair / What-if Evaluation

| Risk cluster | Current candidate | Repaired candidate | Safety verdict | Score delta | Tool/cost delta | Enable recommendation |
| --- | --- | --- | --- | ---: | --- | --- |
| not_targeted | {"api": {"items": [{"method": "GET", "params": {"filter": "name==Birthday Message"}, "path": "/ajo/journey"}], "total_items": 1, "truncated_items": false}, "score": 0.6903, "sql": {"items": ["SELECT \"NAME\" AS campaign_name, \"LASTDEPLOYEDTIME\" AS published_time FROM \"dim_campaign\" LIMIT 50"], "total_items": 1, "truncated_items": false}} | {"api": {"items": [{"method": "GET", "params": {"filter": "name==Birthday Message"}, "path": "/ajo/journey"}], "total_items": 1, "truncated_items": false}, "score": 0.6903, "sql": {"items": ["SELECT \"NAME\" AS campaign_name, \"LASTDEPLOYEDTIME\" AS published_time FROM \"dim_campaign\" LIMIT 50"], "total_items": 1, "truncated_items": false}} | safe | 0.0 | {'tool_delta': 0, 'token_delta': 0, 'runtime_delta': 0.0} | safe_shadow_tie_recommend_canary |
| execution changed? | False | reason | offline shadow evaluation only; packaged SQL_FIRST_API_VERIFY repair execution remains disabled | decision hash | 8b91ef00205c19c0 | |

## Risk-Based Efficiency Controller

Token/runtime savings in this section are estimates only unless packaged execution explicitly changes and validation confirms measured savings.

| Field | Value |
| --- | --- |
| risk_level | low |
| accuracy_risk | low - candidates are separated and schema/API signals are consistent |
| module_policy | low risk: skip expensive diagnostics |
| module_skipped_by_risk | {"items": ["value_retrieval", "shadow_repair", "repair_safety_verifier"], "total_items": 4, "truncated_items": true} |
| token_saved_estimate | 264 |
| runtime_saved_estimate_ms | 25.0 |
| savings_are_estimates | True |
| measured_efficiency_improvement_claimed | False |
| behavior_changed | False |

## Schema Context Voting

Schema context voting is diagnostic guidance for high-risk rows and does not change executed SQL/API plans.

| Field | Value |
| --- | --- |
| active | False |
| schema_vote_agreement | n/a |
| compact_context_safe | n/a |
| fallback_reason | n/a |
| compact_candidate_tables | n/a |
| fallback_candidate_tables | n/a |
| compact_candidate_apis | n/a |
| fallback_candidate_apis | n/a |
| token_delta | n/a |
| behavior_changed | False |

## Value Retrieval Cache

| Field | Value |
| --- | --- |
| status | n/a - value retrieval checkpoint inactive |

## SQL AST Validation

| Field | Value |
| --- | --- |
| status | n/a - SQL AST validation checkpoint inactive |

## Technique Impact Highlight

- Correctness: n/a - no checkpoint correctness role recorded
- Efficiency: n/a - no checkpoint efficiency role recorded
- Dataflow effect: n/a - no checkpoint effect recorded

## Prompt To SQL/API Mapping

```json
{
  "api": {
    "dry_run": true,
    "endpoint": "GET /ajo/journey",
    "endpoint_repair": "n/a - no endpoint repair recorded",
    "live_evidence_available": false,
    "result_preview": "n/a - no API result preview recorded",
    "validation": "ok"
  },
  "context": {
    "candidate_apis": "n/a - no candidate APIs recorded",
    "candidate_tables": "n/a - no candidate tables recorded",
    "confidence": 0.92,
    "context_mode": "candidate",
    "context_mode_note": "recorded in checkpoint/trajectory",
    "estimated_context_tokens": 1314,
    "score_margin": 1.3
  },
  "evidence": {
    "dry_run_only": true,
    "evidence_available": false,
    "explanation": "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing.",
    "live_api_evidence_available": false,
    "overall_evidence_available": false,
    "sql_evidence_available": false,
    "successful_evidence_count": 0,
    "zero_row_uncertain": true
  },
  "normalization": {
    "normalized_query": "n/a - no normalization checkpoint recorded"
  },
  "prompt": "When was the journey 'Birthday Message' published?",
  "route": {
    "api_policy": "n/a - no API policy recorded",
    "confidence": "n/a - no route confidence recorded",
    "mode": "n/a - no prompt router decision",
    "risk": "n/a - no route risk recorded"
  },
  "sql": {
    "preview": "SELECT UPDATEDTIME FROM dim_campaign WHERE CAMPAIGNID IN (SELECT CAMPAIGNID FROM br_campaign_segment WHERE LABELSSEGMENT = 'Birthday Message')",
    "result_preview": "{\"total_items\": 0, \"truncated_items\": false}",
    "row_count": 0,
    "validation": "ok"
  },
  "tokens": {
    "tokens": "n/a - no tokens recorded"
  },
  "truncated_fields": 1
}
```

## Checkpoint Effect Table

| Checkpoint | Stage | Technique | Input | Output | Effect on data flow | Correctness role | Efficiency role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `n/a` | n/a | n/a | n/a | n/a | n/a - no checkpoints recorded | n/a | n/a |
