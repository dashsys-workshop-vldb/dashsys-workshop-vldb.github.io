# DASHSys Prompt-To-Answer Dataflow

## Quality Gate Facts

| Field | Value |
| --- | --- |
| Query ID | `example_031` |
| User query | Which files are available for download in batch 69de8a0e0cc6102b5d11f01e? |
| Strategy | `SQL_FIRST_API_VERIFY` |
| Variant | n/a - not a baseline variant |
| Final answer preview | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| Tool call count | 1 |
| Runtime | 0.009850375005044043 |
| Estimated tokens | 758 |
| Checkpoint count | 21 |
| Candidate context mode | metadata_context_card |
| Context mode note | display-only inferred from checkpoint_07_context_card |

```mermaid
flowchart TD
  subgraph Input
    input_prompt["User Prompt<br/>Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"]
  end
  subgraph Routing
    router["Prompt Router<br/>mode=API_ONLY<br/>api=n/a - no API policy recorded"]
    input_prompt -->|route_prompt| router
  end
  subgraph QueryUnderstanding["Query Understanding"]
    normalizer["Query Normalizer<br/>normalized query"]
    tokens["Query Tokens<br/>domains=audit,batch&lt;br/&gt;entities=1"]
    router -->|clean + extract| normalizer --> tokens
  end
  subgraph ContextSelection["Context Selection"]
    context["Context Mode<br/>metadata_context_card"]
    candidates["Context<br/>tables=none&lt;br/&gt;apis=export_batch_files,export_batch_failed+1"]
    tokens -->|score relevance| context --> candidates
  end
  subgraph Planning
    planner["Planner<br/>SQL_FIRST_API_VERIFY"]
    optimizer["Plan Optimizer<br/>selected=generic_sql_first"]
    candidates -->|metadata + policy| planner --> optimizer
  end
  subgraph SQLPath["SQL Path"]
    sqlgen["SQL Generator<br/>source=none"]
    sqlval["SQL Validator<br/>n/a - no validation step recorded"]
    optimizer -->|SQL step if needed| sqlgen --> sqlval
  end
  subgraph APIPath["API Path"]
    apisel["API Selector<br/>endpoint=/data/foundation/export/batches/69de8a0e0cc6102b5d11f0..."]
    apival["API Validator<br/>ok<br/>dry_run=True"]
    optimizer -->|API policy| apisel --> apival
  end
  subgraph ToolExecution["Tool Execution"]
    tools["Tool Calls<br/>sql=0 api=1<br/>invalid=n/a - no invalid-call metric recorded"]
    sqlval -->|execute_sql| tools
    apival -->|call_api / dry-run| tools
  end
  subgraph EvidenceBus
    evidence["EvidenceBus<br/>SQL evidence: n/a&lt;br/&gt;Live API evidence: no&lt;br/&gt;Dry-run API: yes"]
    tools -->|extract facts| evidence
  end
  subgraph AnswerVerification["Answer Verification"]
    verifier["Verifier<br/>passed=yes&lt;br/&gt;unsupported=0"]
    evidence -->|answer slots + claims| verifier
  end
  subgraph FinalAnswer["Final Answer"]
    answer["Final Answer<br/>Batch file details require live API evidence. Live API verification was not executed because Ado"]
    verifier -->|safe answer| answer
  end
  subgraph Metrics
    metrics["Metrics<br/>tools=1<br/>tokens=758<br/>runtime=0.009850375005044043"]
    answer -->|record trajectory| metrics
  end
```

## SQL And API Preview

| Path | Preview | Validation | Result / Status |
| --- | --- | --- | --- |
| SQL | n/a - no SQL call in trajectory | n/a - no validation step recorded | row_count=n/a - no SQL row count recorded; rows=n/a - no SQL rows preview recorded |
| API | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | ok | dry_run=True; live_api_evidence=False; overall_evidence=False; preview=n/a - no API result preview recorded |

Context mode labels ending in `_inferred` are display-only summaries for the visualization; they are not recorded planner decisions.

## Tool Execution vs Evidence Availability

API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing.

| Metric | Value |
| --- | --- |
| execute_sql calls | 0 |
| call_api calls | 1 |
| valid tool calls | 1 |
| invalid tool calls | n/a - no invalid-call metric recorded |
| endpoint repairs | n/a - no endpoint-repair metric recorded |
| schema hint injections | n/a - no schema-hint metric recorded |
| SQL evidence available | n/a - no SQL call in trajectory |
| live API evidence available | False |
| overall evidence available | False |
| dry-run only | True |
| successful evidence count | 0 |
| zero-row uncertain | n/a - no SQL call in trajectory |

## Research Technique Status

| Technique | Source inspiration | Active? | Effect on dataflow | Correctness impact | Efficiency impact | Visualization checkpoint |
| --- | --- | --- | --- | --- | --- | --- |
| SQLGlot AST validation | SQLGlot | False | AST SQL validation and table/column extraction | detects schema/safety mismatches structurally | diagnostic overhead only | checkpoint_sql_ast_validation |
| Robust schema linking | RSL-SQL | False | Bidirectional schema linking and bridge preservation | keeps relevant tables, columns, and bridges visible | diagnostic overhead only | checkpoint_schema_linking |
| Value/entity retrieval | CHESS | True | Entity-value grounding from local DB samples | grounds named entities and IDs before planning | bounded cached retrieval budget | checkpoint_value_entity_retrieval |
| Query decomposition | DIN-SQL | False | Complex-query decomposition into constraints | preserves complex constraints | diagnostic overhead only | checkpoint_query_decomposition |
| Gated SQL candidates | DIN-SQL / self-correction | False | Hard-case candidate validation before one execution | prevents invalid hard-case SQL from being selected | validates only; executes one selected plan | checkpoint_gated_sql_candidate_selection |
| Query-family examples | DAIL-SQL | False | Optional family hints for LLM SQL | makes technique visibility auditable | optional LLM-only token cost | checkpoint_query_family_examples |
| Span export | OpenAI Agents SDK tracing | True | Local span-style checkpoint export | makes technique visibility auditable | diagnostic overhead only | spans.json |

## SQL AST Validation

`n/a - SQL AST validation checkpoint inactive`

## Technique Impact Highlight

- Correctness: keeps later normalization from changing the user-facing question
- Efficiency: starts one trace without extra tool calls
- Dataflow effect: preserves the original query for reproducibility

## Prompt To SQL/API Mapping

```json
{
  "api": {
    "dry_run": true,
    "endpoint": "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files",
    "endpoint_repair": "n/a - no endpoint repair recorded",
    "live_evidence_available": false,
    "result_preview": "n/a - no API result preview recorded",
    "validation": "ok"
  },
  "context": {
    "candidate_apis": {
      "items": {
        "items": [
          "export_batch_files",
          "export_batch_failed",
          "audit_events"
        ],
        "total_items": 3,
        "truncated_items": false
      },
      "total_items": 3,
      "truncated_items": false
    },
    "candidate_tables": "n/a - no candidate tables recorded",
    "confidence": 0.9,
    "context_mode": "metadata_context_card",
    "context_mode_note": "display-only inferred from checkpoint_07_context_card",
    "estimated_context_tokens": 1000,
    "score_margin": "n/a - no candidate score margin recorded"
  },
  "evidence": {
    "dry_run_only": true,
    "evidence_available": false,
    "explanation": "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing.",
    "live_api_evidence_available": false,
    "overall_evidence_available": false,
    "sql_evidence_available": "n/a - no SQL call in trajectory",
    "successful_evidence_count": 0,
    "zero_row_uncertain": "n/a - no SQL call in trajectory"
  },
  "normalization": {
    "matching_text": "which file are available for download in batch 69de8a0e0cc6102b5d11f01e?",
    "normalized_query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?",
    "rewrites": {
      "items": {
        "items": [
          "important_plurals->singular"
        ],
        "total_items": 1,
        "truncated_items": false
      },
      "total_items": 1,
      "truncated_items": false
    }
  },
  "prompt": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?",
  "route": {
    "api_policy": "n/a - no API policy recorded",
    "confidence": 0.9,
    "mode": "API_ONLY",
    "risk": "medium"
  },
  "sql": {
    "preview": "n/a - no SQL call in trajectory",
    "result_preview": "n/a - no SQL rows preview recorded",
    "row_count": "n/a - no SQL row count recorded",
    "validation": "n/a - no validation step recorded"
  },
  "tokens": {
    "domains": {
      "items": {
        "items": [
          "audit",
          "batch"
        ],
        "total_items": 2,
        "truncated_items": false
      },
      "total_items": 2,
      "truncated_items": false
    },
    "ids": 1
  },
  "truncated_fields": 1
}
```

## Checkpoint Effect Table

| Checkpoint | Stage | Technique | Input | Output | Effect on data flow | Correctness role | Efficiency role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `checkpoint_01_raw_query` | input | raw user query capture |  | {"query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?", "query_id": "example_031", "strategy": "SQL_FIRST_API_VERIFY"} | preserves the original query for reproducibility | keeps later normalization from changing the user-facing question | starts one trace without extra tool calls |
| `checkpoint_00_prompt_router` | prompt routing | LLM_DIRECT / LOCAL_DB_ONLY / SQL_PLUS_API / API_ONLY routing policy | {"query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"} | {"preview": "{\"confidence\": 0.9, \"matched_rules\": {\"items\": {\"items\": [\"api_only:batch\", \"api_only:file\", \"api_only:files\"], \"total_items\": 3, \"truncated_items\": false}, \"total_items\": 3, \"truncated_items\": false}, \"mode\": \"API_ONLY\", \"reason\": \"API/platform family keyword...", "truncated": true} | chooses whether the prompt can be answered directly or needs SQL/API evidence | routes data questions to evidence tools instead of unsupported direct answers | allows clearly conceptual prompts to avoid unnecessary SQL/API calls |
| `checkpoint_simple_prompt_gate` | input routing | simple prompt gate | {"query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"} | {"confidence": 0.9, "is_simple": false, "reason": "API/platform family keyword(s): batch, file, files.", "suggested_action": "USE_DATA_PIPELINE"} | lets an LLM wrapper answer conceptual questions directly while sending evidence questions to the backend | prevents direct answers for data questions that need SQL/API evidence | can skip the data pipeline only for safe conceptual prompts |
| `checkpoint_02_query_normalization` | normalization | data cleaning / query normalization | {"query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"} | {"preview": "{\"matching_text\": \"which file are available for download in batch 69de8a0e0cc6102b5d11f01e?\", \"normalized_query\": \"Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?\", \"rewrites\": {\"items\": {\"items\": [\"important_plurals->singular\"], \"tot...", "truncated": true} | creates matching-friendly text while preserving the original query | improves template and route matching across wording variants | reduces repeated fuzzy matching work downstream |
| `checkpoint_03_query_tokens` | tokenization | domain-aware tokenization/entity extraction | {"normalized_query": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"} | {"domains": {"items": {"items": ["audit", "batch"], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}, "ids": 1} | extracts reusable query fields for routing, planning, and answers | grounds names, IDs, dates, metrics, and statuses before planning | avoids reparsing the query in later modules |
| `checkpoint_04_relevance_scoring` | context selection | attention-style relevance scoring | {"tokens": {"domains": {"items": {"items": ["audit", "batch"], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}, "ids": 1}} | {"preview": "{\"top_answer_families\": {\"items\": {\"items\": [\"batch\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"top_apis\": {\"items\": {\"items\": [\"export_batch_files\", \"export_batch_failed\", \"audit_events\"], \"total_items\": 3, \"t...", "truncated": true} | selects a smaller, more relevant schema/API context | keeps high-signal tables and endpoints near the planner | reduces metadata and prompt tokens when compact metadata is enabled |
| `checkpoint_value_entity_retrieval` | query understanding | CHESS-style value/entity retrieval | {"query_values": {"items": {"items": [{"kind": "batch_id", "text": "69de8a0e0cc6102b5d11f01e"}, {"kind": "id", "text": "69de8a0e0cc6102b5d11f01e"}], "total_items": 2, "truncated_items": false}, "total_items": 2, "truncated_items": false}} | {"preview": "{\"active\": true, \"cache_hit\": true, \"cache_path\": \"[REDACTED]/Desktop/dashsys-workshop-vldb/outputs/cache/value_index_2512512604900919887.json\", \"match_count\": 0, \"query_value_count\": 2, \"retrieval_ms\": 11.784, \"scanned_columns\": 18, \"scanned_tables\": 3, \"trun...", "truncated": true} | grounds query entities against sampled local DB values before planning | helps identify exact names, IDs, statuses, and metrics for SQL/API grounding | uses a cached bounded value index with per-query scan and wall-time budgets |
| `checkpoint_05_query_analysis` | routing | branch prediction / QueryAnalysis | {"domain_type": "UNKNOWN", "route_type": "API_ONLY"} | {"preview": "{\"answer_family\": \"batch\", \"api_templates\": {\"items\": {\"items\": [\"batch_export_files\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"confidence\": 0.3, \"domain_type\": \"UNKNOWN\", \"fast_path\": \"batch_export_files\", \"r...", "truncated": true} | computes shared query understanding once | aligns routing, metadata, planning, and reporting decisions | avoids repeated template and routing analysis |
| `checkpoint_06_lookup_path` | path prediction | TLB-style lookup path prediction | {"answer_family": "batch", "domain_type": "UNKNOWN"} | {"preview": "{\"api_families\": {\"items\": {\"items\": [\"batch_list\", \"recent_batches\", \"batch_details\"], \"total_items\": 3, \"truncated_items\": false}, \"total_items\": 5, \"truncated_items\": true}, \"api_mode\": \"required\", \"family\": \"batch\", \"required_ids\": {\"items\": {\"items\": [\"ba...", "truncated": true} | predicts the relevant table/join/API path | guides relationship-heavy SQL/API selection | filters unrelated schema and endpoint candidates |
| `checkpoint_07_context_card` | metadata packing | huge-page-style compact context card | {"broad_context": false, "lookup_path": "batch"} | {"preview": "{\"estimated_metadata_tokens\": 1000, \"prompt_tokens\": 1673, \"selected_apis\": {\"items\": {\"items\": [\"export_batch_files\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"selected_card_name\": \"batch\", \"selected_columns\":...", "truncated": true} | packs family-relevant context into metadata.json and the filled prompt | keeps required tables, columns, joins, and API candidates visible | limits context size for non-baseline strategies |
| `checkpoint_08_candidate_plans` | planning | pre-execution plan ensemble | {"base_step_count": 1, "strategy": "SQL_FIRST_API_VERIFY"} | {"preview": "{\"candidate_plan_names\": {\"items\": {\"items\": [\"generic_sql_first\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"reason_selected\": \"highest pre-execution validation/relevance/cost score\", \"scores\": {\"generic_sql_fi...", "truncated": true} | selects one plan before execution | prefers validated, family-matched plans | does not execute losing candidate plans |
| `checkpoint_09_plan_optimization` | optimization | compiler-style plan optimization | {"original_step_count": 1} | {"preview": "{\"call_budget_applied\": false, \"optimized_step_count\": 1, \"optimizer_actions\": {\"items\": {\"items\": [\"ensemble selected generic_sql_first\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"original_step_count\": 1, \"rem...", "truncated": true} | removes duplicate, skippable, or unsafe calls before validation | drops unresolved placeholder calls unless explicitly warned | enforces a bounded plan before execution |
| `checkpoint_10_evidence_policy` | evidence policy | API_REQUIRED/API_OPTIONAL/API_SKIP policy | {"answer_family": "batch", "route_type": "API_ONLY"} | {"allowed_api_families": {"items": {"items": ["batch_export_files"], "total_items": 1, "truncated_items": false}, "total_items": 1, "truncated_items": false}, "max_api_calls": 1, "mode": "API_REQUIRED", "reason": "Route is API-only."} | decides when API evidence is required, optional, or unnecessary | keeps API calls for API-only/live families | skips or caps API calls when SQL evidence is enough |
| `checkpoint_11_call_budget` | efficiency control | tool-call budgeting | {"preview": "{\"planned_steps\": {\"items\": {\"items\": [{\"action\": \"api\", \"family\": \"batch_export_files\", \"method\": \"GET\", \"purpose\": \"API parameter template: batch_export_files.\", \"url\": \"/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files\"}], \"total_items\": 1, \"tr...", "truncated": true} | {"final_planned_calls": 1, "max_api_calls": 1, "max_sql_calls": 1, "max_total_tool_calls": 2, "planned_api_calls": 1, "planned_sql_calls": 0} | keeps tool calls within per-family limits | preserves required grounding steps | prevents accidental extra SQL/API calls |
| `checkpoint_12_validation` | validation | SQL/API safety validation | {"preview": "{\"optimized_steps\": {\"items\": {\"items\": [{\"action\": \"api\", \"family\": \"batch_export_files\", \"method\": \"GET\", \"purpose\": \"API parameter template: batch_export_files.\", \"url\": \"/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files\"}], \"total_items\": 1, \"...", "truncated": true} | {"api_validation_status": {"items": {"items": [{"errors": {"total_items": 0, "truncated_items": false}, "ok": true}], "total_items": 1, "truncated_items": false}, "total_items": 1, "truncated_items": false}} | records whether planned SQL/API calls were safe to execute | blocks unsafe SQL and unknown/unresolved API calls | prevents wasted execution on invalid calls |
| `checkpoint_13_tool_execution` | execution | SQL/API tool execution | {"validated_step_count": 1} | {"preview": "{\"api_calls_executed\": 1, \"api_results\": {\"items\": {\"items\": [{\"result_preview\": {\"error\": \"Adobe credentials unavailable; API call not executed.\", \"result_preview\": null, \"dry_run\": true, \"endpoint\": \"/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/f...", "truncated": true} | captures the actual SQL/API evidence gathered by the backend | records row counts, dry-run state, and API status for final answer grounding | makes tool-call count and result previews explicit |
| `checkpoint_14_evidence_bus` | evidence forwarding | operand forwarding / EvidenceBus | {"tool_result_count": 1} | {} | forwards structured facts to API params and answer slots | passes exact IDs, names, counts, timestamps, and statuses without text guessing | avoids repeated lookup or reparsing work |
| `checkpoint_15_answer_slots` | answer synthesis | structured answer slot extraction | {"tool_result_count": 1} | {"preview": "{\"answer_intent\": \"LIST\", \"discrepancy_flags\": {\"sql_api_discrepancy\": false}, \"dry_run_flags\": {\"dry_run\": true}, \"missing_slots\": {\"items\": {\"items\": [\"list_items\"], \"total_items\": 1, \"truncated_items\": false}, \"total_items\": 1, \"truncated_items\": false}, \"s...", "truncated": true} | turns raw tool results into typed evidence fields | makes final response generation evidence-grounded | keeps answer context compact |
| `checkpoint_16_answer_verification` | answer verification | claim verification / groundedness checking | {"claim_count": 0, "slots_present": {"items": {"items": ["dry_run"], "total_items": 1, "truncated_items": false}, "total_items": 1, "truncated_items": false}} | {"errors": {"total_items": 0, "truncated_items": false}, "rewrite_applied": false, "supported_claims_count": 0, "unsupported_claims_count": 0, "verifier_passed": true} | checks final-answer claims against SQL/API evidence | blocks unsupported numbers, entities, timestamps, statuses, and dry-run API confirmation | rewrites safely without extra tool calls |
| `checkpoint_17_answer_reranking` | answer selection | deterministic answer reranking | {"answer_family": "batch"} | {"candidate_count": 0, "selected_candidate_type": "base", "selection_reason": "best verifier-passing answer"} | selects the safest answer from same-evidence candidates | prefers verifier-passing and intent-matched answers | uses no additional SQL/API/LLM calls |
| `checkpoint_18_final_answer` | final response | concise grounded final response | {"verifier_passed": true} | {"answer_length": 127, "final_answer": "Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.", "final_token_estimate": 20} | returns the final concise answer to the agent harness | final answer remains tied to evidence and caveats | keeps response concise |
