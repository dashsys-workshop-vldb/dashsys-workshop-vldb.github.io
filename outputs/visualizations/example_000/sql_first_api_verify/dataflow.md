# DASHSys Prompt-To-Answer Dataflow

## Quality Gate Facts

| Field | Value |
| --- | --- |
| Query ID | `example_000` |
| User query | When was the journey 'Birthday Message' published? |
| Strategy | `SQL_FIRST_API_VERIFY` |
| Variant | n/a - not a baseline variant |
| Final answer preview | The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable. |
| Tool call count | 2 |
| Runtime | 0.012236207956448197 |
| Estimated tokens | 950 |
| Checkpoint count | 24 |
| Candidate context mode | metadata_context_card |
| Context mode note | display-only inferred from checkpoint_07_context_card |

```mermaid
flowchart TD
  subgraph Input
    input_prompt["User Prompt<br/>When was the journey &#x27;Birthday Message&#x27; published?"]
  end
  subgraph Routing
    router["Prompt Router<br/>mode=SQL_PLUS_API<br/>api=n/a - no API policy recorded"]
    input_prompt -->|route_prompt| router
  end
  subgraph QueryUnderstanding["Query Understanding"]
    normalizer["Query Normalizer<br/>normalized query"]
    tokens["Query Tokens<br/>domains=journey_campaign&lt;br/&gt;entities=Birthday Message&lt;br/&gt;status=published"]
    router -->|clean + extract| normalizer --> tokens
  end
  subgraph ContextSelection["Context Selection"]
    context["Context Mode<br/>metadata_context_card"]
    candidates["Context<br/>tables=dim_campaign&lt;br/&gt;apis=journey_list,schema_registry_schema+1"]
    tokens -->|score relevance| context --> candidates
  end
  subgraph Planning
    planner["Planner<br/>SQL_FIRST_API_VERIFY"]
    optimizer["Plan Optimizer<br/>selected=generic_sql_first"]
    candidates -->|metadata + policy| planner --> optimizer
  end
  subgraph SQLPath["SQL Path"]
    sqlgen["SQL Generator<br/>tables=dim_campaign&lt;br/&gt;rows=2"]
    sqlval["SQL Validator<br/>ok"]
    optimizer -->|SQL step if needed| sqlgen --> sqlval
  end
  subgraph APIPath["API Path"]
    apisel["API Selector<br/>endpoint=/ajo/journey"]
    apival["API Validator<br/>ok<br/>dry_run=True"]
    optimizer -->|API policy| apisel --> apival
  end
  subgraph ToolExecution["Tool Execution"]
    tools["Tool Calls<br/>sql=1 api=1<br/>invalid=n/a - no invalid-call metric recorded"]
    sqlval -->|execute_sql| tools
    apival -->|call_api / dry-run| tools
  end
  subgraph EvidenceBus
    evidence["EvidenceBus<br/>SQL evidence: yes&lt;br/&gt;Live API evidence: no&lt;br/&gt;Dry-run API: yes"]
    tools -->|extract facts| evidence
  end
  subgraph AnswerVerification["Answer Verification"]
    verifier["Verifier<br/>passed=yes&lt;br/&gt;unsupported=0"]
    evidence -->|answer slots + claims| verifier
  end
  subgraph FinalAnswer["Final Answer"]
    answer["Final Answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null publi"]
    verifier -->|safe answer| answer
  end
  subgraph Metrics
    metrics["Metrics<br/>tools=2<br/>tokens=950<br/>runtime=0.012236207956448197"]
    answer -->|record trajectory| metrics
  end
```

## SQL And API Preview

| Path | Preview | Validation | Result / Status |
| --- | --- | --- | --- |
| SQL | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | ok | row_count=2; rows={"items": {"items": [{"campaign_name": "Birthday Message"}, {"campaign_name": "Gold Tier Welcome Email"}], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false} |
| API | GET /ajo/journey | ok | dry_run=True; live_api_evidence=False; overall_evidence=True; preview=n/a - no API result preview recorded |

Context mode labels ending in `_inferred` are display-only summaries for the visualization; they are not recorded planner decisions.

## Tool Execution vs Evidence Availability

SQL evidence is available. API tool was invoked and validated, but live API evidence was unavailable because Adobe credentials were missing.

| Metric | Value |
| --- | --- |
| execute_sql calls | 1 |
| call_api calls | 1 |
| valid tool calls | 2 |
| invalid tool calls | n/a - no invalid-call metric recorded |
| endpoint repairs | n/a - no endpoint-repair metric recorded |
| schema hint injections | n/a - no schema-hint metric recorded |
| SQL evidence available | True |
| live API evidence available | False |
| overall evidence available | True |
| dry-run only | True |
| successful evidence count | 1 |
| zero-row uncertain | False |

## Research Technique Status

| Technique | Source inspiration | Active? | Effect on dataflow | Correctness impact | Efficiency impact | Visualization checkpoint |
| --- | --- | --- | --- | --- | --- | --- |
| SQLGlot AST validation | SQLGlot | True | AST SQL validation and table/column extraction | detects schema/safety mismatches structurally | diagnostic overhead only | checkpoint_sql_ast_validation |
| Robust schema linking | RSL-SQL | False | Bidirectional schema linking and bridge preservation | keeps relevant tables, columns, and bridges visible | diagnostic overhead only | checkpoint_schema_linking |
| Value/entity retrieval | CHESS | True | Entity-value grounding from local DB samples | grounds named entities and IDs before planning | bounded cached retrieval budget | checkpoint_value_entity_retrieval |
| Query decomposition | DIN-SQL | True | Complex-query decomposition into constraints | preserves complex constraints | diagnostic overhead only | checkpoint_query_decomposition |
| Gated SQL candidates | DIN-SQL / self-correction | True | Hard-case candidate validation before one execution | prevents invalid hard-case SQL from being selected | validates only; executes one selected plan | checkpoint_gated_sql_candidate_selection |
| Query-family examples | DAIL-SQL | False | Optional family hints for LLM SQL | makes technique visibility auditable | optional LLM-only token cost | checkpoint_query_family_examples |
| Span export | OpenAI Agents SDK tracing | True | Local span-style checkpoint export | makes technique visibility auditable | diagnostic overhead only | spans.json |

## Value Retrieval Cache

| Field | Value |
| --- | --- |
| cache_hit | True |
| cache_key_algorithm | sha256 |
| cache_reproducible | True |
| retrieval_ms | n/a |
| cold_cache_build_ms | n/a |
| warm_cache_lookup_ms | n/a |
| value_retrieval_budget_exceeded | n/a |
| match_count | 1 |

## SQL AST Validation

| Field | Value |
| --- | --- |
| parsed_ok | True |
| parse_errors | n/a |
| selected_tables | {"items": {"items": ["dim_campaign"], "total_items": 1, "truncated_items": false}, "total_items": 1, "truncated_items": false} |
| selected_columns | {"items": {"items": ["LASTDEPLOYEDTIME", "NAME"], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false} |
| unknown_tables | n/a |
| unknown_columns | n/a |
| destructive_sql_detected | False |
| closest_table_suggestions | n/a |
| closest_column_suggestions | n/a |

## Technique Impact Highlight

- Correctness: keeps later normalization from changing the user-facing question
- Efficiency: starts one trace without extra tool calls
- Dataflow effect: preserves the original query for reproducibility

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
    "candidate_apis": {
      "items": {
        "items": [
          "journey_list",
          "schema_registry_schema",
          "unified_tag_detail"
        ],
        "total_items": 3,
        "truncated_items": false
      },
      "total_items": 3,
      "truncated_items": false
    },
    "candidate_tables": {
      "items": {
        "items": [
          "dim_campaign"
        ],
        "total_items": 1,
        "truncated_items": false
      },
      "total_items": 1,
      "truncated_items": false
    },
    "confidence": 0.88,
    "context_mode": "metadata_context_card",
    "context_mode_note": "display-only inferred from checkpoint_07_context_card",
    "estimated_context_tokens": 374,
    "score_margin": "n/a - no candidate score margin recorded"
  },
  "evidence": {
    "dry_run_only": true,
    "evidence_available": true,
    "explanation": "SQL evidence is available. API tool was invoked and validated, but live API evidence was unavailable because Adobe credentials were missing.",
    "live_api_evidence_available": false,
    "overall_evidence_available": true,
    "sql_evidence_available": true,
    "successful_evidence_count": 1,
    "zero_row_uncertain": false
  },
  "normalization": {
    "matching_text": "when was the journey 'birthday message' published?",
    "normalized_query": "When was the journey 'Birthday Message' published?"
  },
  "prompt": "When was the journey 'Birthday Message' published?",
  "route": {
    "api_policy": "n/a - no API policy recorded",
    "confidence": 0.88,
    "mode": "SQL_PLUS_API",
    "risk": "medium"
  },
  "sql": {
    "preview": "SELECT \"NAME\" AS campaign_name, \"LASTDEPLOYEDTIME\" AS published_time FROM \"dim_campaign\" LIMIT 50",
    "result_preview": "{\"items\": {\"items\": [{\"campaign_name\": \"Birthday Message\"}, {\"campaign_name\": \"Gold Tier Welcome Email\"}], \"total_items\": 2, \"truncated_items\": false}, \"total_items\": 2, \"truncated_items\": false}",
    "row_count": 2,
    "validation": "ok"
  },
  "tokens": {
    "domains": {
      "items": {
        "items": [
          "journey_campaign"
        ],
        "total_items": 1,
        "truncated_items": false
      },
      "total_items": 1,
      "truncated_items": false
    },
    "quoted_entities": {
      "items": {
        "items": [
          "Birthday Message"
        ],
        "total_items": 1,
        "truncated_items": false
      },
      "total_items": 1,
      "truncated_items": false
    },
    "statuses": {
      "items": {
        "items": [
          "published"
        ],
        "total_items": 1,
        "truncated_items": false
      },
      "total_items": 1,
      "truncated_items": false
    }
  },
  "truncated_fields": 1
}
```

## Checkpoint Effect Table

| Checkpoint | Stage | Technique | Input | Output | Effect on data flow | Correctness role | Efficiency role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `checkpoint_01_raw_query` | input | raw user query capture |  | {"query": "When was the journey 'Birthday Message' published?", "query_id": "example_000", "strategy": "SQL_FIRST_API_VERIFY"} | preserves the original query for reproducibility | keeps later normalization from changing the user-facing question | starts one trace without extra tool calls |
| `checkpoint_00_prompt_router` | prompt routing | LLM_DIRECT / LOCAL_DB_ONLY / SQL_PLUS_API / API_ONLY routing policy | {"query": "When was the journey 'Birthday Message' published?"} | {"preview": "{\"confidence\": 0.88, \"matched_rules\": {\"items\": {\"items\": [\"sql_plus_api:published\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"mode\": \"SQL_PLUS_API\", \"reason\": \"Live/status keyword(s) require SQL grounding plus...", "truncated": true} | chooses whether the prompt can be answered directly or needs SQL/API evidence | routes data questions to evidence tools instead of unsupported direct answers | allows clearly conceptual prompts to avoid unnecessary SQL/API calls |
| `checkpoint_simple_prompt_gate` | input routing | simple prompt gate | {"query": "When was the journey 'Birthday Message' published?"} | {"confidence": 0.88, "is_simple": false, "reason": "Live/status keyword(s) require SQL grounding plus API verification: published.", "suggested_action": "USE_DATA_PIPELINE"} | lets an LLM wrapper answer conceptual questions directly while sending evidence questions to the backend | prevents direct answers for data questions that need SQL/API evidence | can skip the data pipeline only for safe conceptual prompts |
| `checkpoint_02_query_normalization` | normalization | data cleaning / query normalization | {"query": "When was the journey 'Birthday Message' published?"} | {"matching_text": "when was the journey 'birthday message' published?", "normalized_query": "When was the journey 'Birthday Message' published?"} | creates matching-friendly text while preserving the original query | improves template and route matching across wording variants | reduces repeated fuzzy matching work downstream |
| `checkpoint_03_query_tokens` | tokenization | domain-aware tokenization/entity extraction | {"normalized_query": "When was the journey 'Birthday Message' published?"} | {"preview": "{\"domains\": {\"items\": {\"items\": [\"journey_campaign\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"quoted_entities\": {\"items\": {\"items\": [\"Birthday Message\"], \"total_items\": 1, \"truncated_items\": false}, \"total_ite...", "truncated": true} | extracts reusable query fields for routing, planning, and answers | grounds names, IDs, dates, metrics, and statuses before planning | avoids reparsing the query in later modules |
| `checkpoint_04_relevance_scoring` | context selection | attention-style relevance scoring | {"preview": "{\"tokens\": {\"domains\": {\"items\": {\"items\": [\"journey_campaign\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"quoted_entities\": {\"items\": {\"items\": [\"Birthday Message\"], \"total_items\": 1, \"truncated_items\": false},...", "truncated": true} | {"preview": "{\"top_answer_families\": {\"items\": {\"items\": [\"journey_published\", \"inactive_journeys\"], \"total_items\": 2, \"truncated_items\": false}, \"total_items\": 2, \"truncated_items\": false}, \"top_apis\": {\"items\": {\"items\": [\"journey_list\", \"schema_registry_schema\", \"unifie...", "truncated": true} | selects a smaller, more relevant schema/API context | keeps high-signal tables and endpoints near the planner | reduces metadata and prompt tokens when compact metadata is enabled |
| `checkpoint_value_entity_retrieval` | query understanding | CHESS-style value/entity retrieval | {"query_values": {"items": {"items": [{"kind": "quoted_entity", "text": "Birthday Message"}, {"kind": "status", "text": "published"}], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}} | {"preview": "{\"active\": true, \"cache_hit\": true, \"cache_key\": \"fa917ba84b79c5a3\", \"cache_key_algorithm\": \"sha256\", \"cache_reproducible\": true, \"match_count\": 1, \"matches\": {\"items\": {\"items\": [{\"confidence\": 1.0, \"kind\": \"quoted_entity\", \"match_type\": \"exact\", \"matched_col...", "truncated": true} | grounds query entities against sampled local DB values before planning | helps identify exact names, IDs, statuses, and metrics for SQL/API grounding | uses a cached bounded value index with per-query scan and wall-time budgets |
| `checkpoint_query_decomposition` | query understanding | DIN-SQL-style deterministic query decomposition | {"preview": "{\"query\": \"When was the journey 'Birthday Message' published?\", \"tokens\": {\"domains\": {\"items\": {\"items\": [\"journey_campaign\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"quoted_entities\": {\"items\": {\"items\": [\"B...", "truncated": true} | {"preview": "{\"active\": true, \"expected_answer_shape\": \"short_fact\", \"required_entities\": {\"items\": {\"items\": [\"Birthday Message\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"required_filters\": {\"items\": {\"items\": [\"published...", "truncated": true} | breaks complex prompts into entities, filters, joins, and answer-shape constraints | helps SQL/API planning preserve requested constraints | skips simple queries and uses no LLM/tool calls |
| `checkpoint_05_query_analysis` | routing | branch prediction / QueryAnalysis | {"domain_type": "JOURNEY_CAMPAIGN", "route_type": "SQL_THEN_API"} | {"preview": "{\"answer_family\": \"journey_published\", \"api_templates\": {\"items\": {\"items\": [\"journey_by_name\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"confidence\": 0.8, \"domain_type\": \"JOURNEY_CAMPAIGN\", \"fast_path\": \"journ...", "truncated": true} | computes shared query understanding once | aligns routing, metadata, planning, and reporting decisions | avoids repeated template and routing analysis |
| `checkpoint_06_lookup_path` | path prediction | TLB-style lookup path prediction | {"answer_family": "journey_published", "domain_type": "JOURNEY_CAMPAIGN"} | {"preview": "{\"api_families\": {\"items\": {\"items\": [\"journey_by_name\", \"journey_inactive\", \"journey_list\"], \"total_items\": 3, \"truncated_items\": false}, \"total_items\": 3, \"truncated_items\": false}, \"api_mode\": \"optional\", \"family\": \"journey_campaign\", \"required_ids\": {\"item...", "truncated": true} | predicts the relevant table/join/API path | guides relationship-heavy SQL/API selection | filters unrelated schema and endpoint candidates |
| `checkpoint_07_context_card` | metadata packing | huge-page-style compact context card | {"broad_context": false, "lookup_path": "journey_campaign"} | {"preview": "{\"estimated_metadata_tokens\": 374, \"prompt_tokens\": 937, \"selected_apis\": {\"items\": {\"items\": [\"journey_list\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"selected_card_name\": \"journey_campaign\", \"selected_column...", "truncated": true} | packs family-relevant context into metadata.json and the filled prompt | keeps required tables, columns, joins, and API candidates visible | limits context size for non-baseline strategies |
| `checkpoint_08_candidate_plans` | planning | pre-execution plan ensemble | {"base_step_count": 2, "strategy": "SQL_FIRST_API_VERIFY"} | {"preview": "{\"candidate_plan_names\": {\"items\": {\"items\": [\"generic_sql_first\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"reason_selected\": \"highest pre-execution validation/relevance/cost score\", \"scores\": {\"generic_sql_fi...", "truncated": true} | selects one plan before execution | prefers validated, family-matched plans | does not execute losing candidate plans |
| `checkpoint_09_plan_optimization` | optimization | compiler-style plan optimization | {"original_step_count": 2} | {"preview": "{\"call_budget_applied\": false, \"optimized_step_count\": 2, \"optimizer_actions\": {\"items\": {\"items\": [\"ensemble selected generic_sql_first\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"original_step_count\": 2, \"rem...", "truncated": true} | removes duplicate, skippable, or unsafe calls before validation | drops unresolved placeholder calls unless explicitly warned | enforces a bounded plan before execution |
| `checkpoint_10_evidence_policy` | evidence policy | API_REQUIRED/API_OPTIONAL/API_SKIP policy | {"answer_family": "journey_published", "route_type": "SQL_THEN_API"} | {"preview": "{\"allowed_api_families\": {\"items\": {\"items\": [\"journey_by_name\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"max_api_calls\": 1, \"mode\": \"API_OPTIONAL\", \"reason\": \"Live/platform verification may improve the answer...", "truncated": true} | decides when API evidence is required, optional, or unnecessary | keeps API calls for API-only/live families | skips or caps API calls when SQL evidence is enough |
| `checkpoint_11_call_budget` | efficiency control | tool-call budgeting | {"preview": "{\"planned_steps\": {\"items\": {\"items\": [{\"action\": \"sql\", \"family\": \"journey_campaign_published\", \"purpose\": \"Fast-path SQL grounding.\", \"sql\": \"SELECT \\\"NAME\\\" AS campaign_name, \\\"LASTDEPLOYEDTIME\\\" AS published_time FROM \\\"dim_campaign\\\" LIMIT 50\"}, {\"action\"...", "truncated": true} | {"final_planned_calls": 2, "max_api_calls": 1, "max_sql_calls": 1, "max_total_tool_calls": 2, "planned_api_calls": 1, "planned_sql_calls": 1} | keeps tool calls within per-family limits | preserves required grounding steps | prevents accidental extra SQL/API calls |
| `checkpoint_gated_sql_candidate_selection` | planning | hard-case gated SQL candidate validation | {"trigger_reasons": {"items": {"items": ["complex_query_decomposition", "value_match_not_used_by_sql"], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}} | {"preview": "{\"preview\": \"{\\\"active\\\": true, \\\"hard_case_triggered\\\": true, \\\"trigger_reasons\\\": {\\\"items\\\": [\\\"complex_query_decomposition\\\", \\\"value_match_not_used_by_sql\\\"], \\\"total_items\\\": 2, \\\"truncated_items\\\": false}, \\\"candidate_count\\\": 1, \\\"candidate_sql_sources...", "truncated": true} | validates hard-case SQL candidates before execution without executing losing candidates | selects only validator- and AST-passing SQL candidates | executes only one selected candidate in packaged SQL_FIRST_API_VERIFY mode |
| `checkpoint_12_validation` | validation | SQL/API safety validation | {"preview": "{\"optimized_steps\": {\"items\": {\"items\": [{\"action\": \"sql\", \"family\": \"journey_campaign_published\", \"purpose\": \"Fast-path SQL grounding.\", \"sql\": \"SELECT \\\"NAME\\\" AS campaign_name, \\\"LASTDEPLOYEDTIME\\\" AS published_time FROM \\\"dim_campaign\\\" LIMIT 50\"}, {\"actio...", "truncated": true} | {"preview": "{\"api_validation_status\": {\"items\": {\"items\": [{\"errors\": {\"total_items\": 0, \"truncated_items\": false}, \"ok\": true}], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"sql_validation_status\": {\"items\": {\"items\": [{\"erro...", "truncated": true} | records whether planned SQL/API calls were safe to execute | blocks unsafe SQL and unknown/unresolved API calls | prevents wasted execution on invalid calls |
| `checkpoint_sql_ast_validation` | validation | SQLGlot AST-based SQL validation and extraction | {"sql_call_count": 1} | {"preview": "{\"destructive_sql_detected\": false, \"parsed_ok\": true, \"selected_columns\": {\"items\": {\"items\": [\"LASTDEPLOYEDTIME\", \"NAME\"], \"total_items\": 2, \"truncated_items\": false}, \"total_items\": 2, \"truncated_items\": false}, \"selected_tables\": {\"items\": {\"items\": [\"dim_...", "truncated": true} | adds AST-level table and column extraction after existing SQL validation | detects unsafe SQL and schema mismatches with parser-backed structure | provides precise feedback without extra SQL tool calls |
| `checkpoint_13_tool_execution` | execution | SQL/API tool execution | {"validated_step_count": 2} | {"preview": "{\"api_calls_executed\": 1, \"api_results\": {\"items\": {\"items\": [{\"result_preview\": {\"error\": \"Adobe credentials unavailable; API call not executed.\", \"result_preview\": null, \"dry_run\": true, \"endpoint\": \"/ajo/journey\", \"method\": \"GET\", \"ok\": false, \"params\": {\"f...", "truncated": true} | captures the actual SQL/API evidence gathered by the backend | records row counts, dry-run state, and API status for final answer grounding | makes tool-call count and result previews explicit |
| `checkpoint_14_evidence_bus` | evidence forwarding | operand forwarding / EvidenceBus | {"tool_result_count": 2} | {"evidence": {"names": {"items": {"items": ["Birthday Message", "Gold Tier Welcome Email"], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}}} | forwards structured facts to API params and answer slots | passes exact IDs, names, counts, timestamps, and statuses without text guessing | avoids repeated lookup or reparsing work |
| `checkpoint_15_answer_slots` | answer synthesis | structured answer slot extraction | {"tool_result_count": 2} | {"preview": "{\"answer_intent\": \"WHEN\", \"discrepancy_flags\": {\"sql_api_discrepancy\": false}, \"dry_run_flags\": {\"dry_run\": true}, \"missing_slots\": {\"items\": {\"items\": [\"timestamp\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"sl...", "truncated": true} | turns raw tool results into typed evidence fields | makes final response generation evidence-grounded | keeps answer context compact |
| `checkpoint_16_answer_verification` | answer verification | claim verification / groundedness checking | {"claim_count": 2, "slots_present": {"items": {"items": ["entity_names", "counts", "sql_row_count"], "total_items": 3, "truncated_items": false}, "total_items": 5, "truncated_items": true}} | {"errors": {"total_items": 0, "truncated_items": false}, "rewrite_applied": false, "supported_claims_count": 2, "unsupported_claims_count": 0, "verifier_passed": true} | checks final-answer claims against SQL/API evidence | blocks unsupported numbers, entities, timestamps, statuses, and dry-run API confirmation | rewrites safely without extra tool calls |
| `checkpoint_17_answer_reranking` | answer selection | deterministic answer reranking | {"answer_family": "journey_published"} | {"candidate_count": 0, "selected_candidate_type": "base", "selection_reason": "best verifier-passing answer"} | selects the safest answer from same-evidence candidates | prefers verifier-passing and intent-matched answers | uses no additional SQL/API/LLM calls |
| `checkpoint_18_final_answer` | final response | concise grounded final response | {"verifier_passed": true} | {"preview": "{\"answer_length\": 199, \"final_answer\": \"The journey \\\"Birthday Message\\\" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.\", \"final_token_est...", "truncated": true} | returns the final concise answer to the agent harness | final answer remains tied to evidence and caveats | keeps response concise |
