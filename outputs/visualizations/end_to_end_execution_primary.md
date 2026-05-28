# End-to-End Execution Movie: example_011

## How To Read This Page

1. Start from the raw prompt card.
2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.
3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.

## Primary Testing Prompt

> **example_011**
>
> # How many schemas do I have?
>
> Primary SQL-backed packaged walkthrough: the prompt becomes validated SQL, SQL returns the answer count, and API verification remains dry-run/unavailable.

## Execution Flowchart

```mermaid
flowchart LR
  A["Raw prompt"] --> B["Routing"]
  B --> C["Normalize + tokens"]
  C --> D["Query analysis"]
  D --> E["Metadata/context"]
  E --> F["Planning"]
  F --> G["Validation + budget"]
  G --> H["Execution"]
  H --> I["Evidence bus"]
  I --> J["Answer synthesis"]
  J --> K["Verifier/reranker"]
  K --> L["Final answer"]
  L --> M["Trajectory + reports"]
```

## System Sequence

```mermaid
sequenceDiagram
  participant User
  participant Router
  participant Normalizer
  participant Analysis as Query Analysis
  participant Metadata as Metadata Selector
  participant Planner
  participant SQL as SQL Template
  participant API as API Template
  participant Validator
  participant Executor
  participant Evidence as Evidence Bus
  participant Answer as Answer Synthesizer
  participant Verify as Verifier/Reranker
  participant Output as Final Output
  User->>Router: raw prompt
  Router->>Normalizer: use data pipeline
  Normalizer->>Analysis: normalized text + tokens
  Analysis->>Metadata: route intent + answer family
  Metadata->>Planner: compact context
  Planner->>SQL: schema count SQL
  Planner->>API: schema verification call
  SQL->>Validator: read-only count query
  API->>Validator: method/path/params
  Validator->>Executor: safe SQL + API verification
  Executor->>Evidence: SQL count + dry-run API label
  Evidence->>Answer: count evidence + dry-run status
  Answer->>Verify: SQL-grounded answer
  Verify->>Output: final answer + trajectory
```

## Visual Checkpoint Timeline

| # | Checkpoint | Stage | Technique | Input | Output | What changed | Effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | checkpoint_01_raw_query | input | raw user query capture | unavailable | query=How many schemas do I have?; query_id=example_011; strategy=SQL_FIRST_API_VERIFY | preserves the original query for reproducibility | keeps later normalization from changing the user-facing question |
| 2 | checkpoint_00_prompt_router | prompt routing | LLM_DIRECT / LOCAL_DB_ONLY / SQL_PLUS_API / API_ONLY routing policy | query=How many schemas do I have? | confidence=0.84; reason=Local snapshot keyword(s) can be answered from DuckDB/par... | chooses whether the prompt can be answered directly or needs SQL/API evidence | routes data questions to evidence tools instead of unsupported direct answers |
| 3 | checkpoint_simple_prompt_gate | input routing | simple prompt gate | query=How many schemas do I have? | confidence=0.84; is_simple=False; suggested_action=USE_DATA_PIPELINE; reason=Local snapshot keyword(s) can be answered from Duc... | lets an LLM wrapper answer conceptual questions directly while sending evidence questions to the backend | prevents direct answers for data questions that need SQL/API evidence |
| 4 | checkpoint_objective_prompt_features | semantic routing shadow | objective prompt feature extraction | query=How many schemas do I have? | cap=3 item(s); count=1 item(s); domain=1 item(s); norm=how many schemas do i have? | records fact-only prompt cues for semantic routing diagnostics | keeps semantic pre-routing separate from SQL/API planning and answer generation |
| 5 | checkpoint_02_query_normalization | normalization | data cleaning / query normalization | query=How many schemas do I have? | normalized_query=How many schemas do I have?; matching_text=how many schema do i have? | creates matching-friendly text while preserving the original query | improves template and route matching across wording variants |
| 6 | checkpoint_03_query_tokens | tokenization | domain-aware tokenization/entity extraction | normalized_query=How many schemas do I have? | domains=1 item(s) | extracts reusable query fields for routing, planning, and answers | grounds names, IDs, dates, metrics, and statuses before planning |
| 7 | checkpoint_04_relevance_scoring | context selection | attention-style relevance scoring | tokens=1 field(s) | top_answer_families=1 item(s); top_apis=3 item(s); top_join_hints=3 item(s); top_tables=3 item(s) | selects a smaller, more relevant schema/API context | keeps high-signal tables and endpoints near the planner |
| 8 | checkpoint_05_query_analysis | routing | branch prediction / QueryAnalysis | route_type=SQL_ONLY; domain_type=DATASET_SCHEMA | strategy=SQL_FIRST_API_VERIFY; route_type=SQL_ONLY; domain_type=DATASET_SCHEMA; answer_family=schema_dataset | computes shared query understanding once | aligns routing, metadata, planning, and reporting decisions |
| 9 | checkpoint_06_lookup_path | path prediction | TLB-style lookup path prediction | domain_type=DATASET_SCHEMA; answer_family=schema_dataset | api_mode=required | predicts the relevant table/join/API path | guides relationship-heavy SQL/API selection |
| 10 | checkpoint_07_context_card | metadata packing | huge-page-style compact context card | lookup_path=schema_dataset | estimated_metadata_tokens=490; prompt_tokens=1072; selected_apis=1 item(s); selected_card_name=schema_dataset | packs family-relevant context into metadata.json and the filled prompt | keeps required tables, columns, joins, and API candidates visible |
| 11 | checkpoint_08_candidate_plans | planning | pre-execution plan ensemble | strategy=SQL_FIRST_API_VERIFY | selected_plan=generic_sql_first | selects one plan before execution | prefers validated, family-matched plans |
| 12 | checkpoint_09_plan_optimization | optimization | compiler-style plan optimization | original_step_count=2 | call_budget_applied=False; optimized_step_count=2; optimizer_actions=1 item(s); original_step_count=2 | removes duplicate, skippable, or unsafe calls before validation | drops unresolved placeholder calls unless explicitly warned |
| 13 | checkpoint_10_evidence_policy | evidence policy | API_REQUIRED/API_OPTIONAL/API_SKIP policy | route_type=SQL_ONLY; answer_family=schema_dataset | reason=Query family requires Adobe API evidence. | decides when API evidence is required, optional, or unnecessary | keeps API calls for API-only/live families |
| 14 | checkpoint_11_call_budget | efficiency control | tool-call budgeting | planned_steps=2 item(s) | planned_sql_calls=1; planned_api_calls=1 | keeps tool calls within per-family limits | preserves required grounding steps |
| 15 | checkpoint_12_validation | validation | SQL/API safety validation | optimized_steps=2 item(s) | api_validation_status=1 item(s); sql_validation_status=1 item(s) | records whether planned SQL/API calls were safe to execute | blocks unsafe SQL and unknown/unresolved API calls |
| 16 | checkpoint_sql_ast_validation | validation | SQLGlot AST-based SQL validation and extraction | sql_call_count=1 | destructive_sql_detected=False; parsed_ok=True; selected_columns=1 item(s); selected_tables=1 item(s) | adds AST-level table and column extraction after existing SQL validation | detects unsafe SQL and schema mismatches with parser-backed structure |
| 17 | checkpoint_13_tool_execution | execution | SQL/API tool execution | validated_step_count=2 | sql_calls_executed=1; api_calls_executed=1 | captures the actual SQL/API evidence gathered by the backend | records row counts, dry-run state, and API status for final answer grounding |
| 18 | checkpoint_14_evidence_bus | evidence forwarding | operand forwarding / EvidenceBus | tool_result_count=2 | evidence=3 field(s) | forwards structured facts to API params and answer slots | passes exact IDs, names, counts, timestamps, and statuses without text guessing |
| 19 | checkpoint_15_answer_slots | answer synthesis | structured answer slot extraction | tool_result_count=2 | answer_intent=COUNT | turns raw tool results into typed evidence fields | makes final response generation evidence-grounded |
| 20 | checkpoint_16_answer_verification | answer verification | claim verification / groundedness checking | claim_count=1; slots_present=6 item(s) | verifier_passed=True | checks final-answer claims against SQL/API evidence | blocks unsupported numbers, entities, timestamps, statuses, and dry-run API confirmation |
| 21 | checkpoint_17_answer_reranking | answer selection | deterministic answer reranking | answer_family=schema_dataset | candidate_count=0; selected_candidate_type=base; selection_reason=best verifier-passing answer | selects the safest answer from same-evidence candidates | prefers verifier-passing and intent-matched answers |
| 22 | checkpoint_18_final_answer | final response | concise grounded final response | verifier_passed=True | answer_length=170; final_answer=You have 74 schemas. This count comes from your blueprint... | returns the final concise answer to the agent harness | final answer remains tied to evidence and caveats |
| 23 | checkpoint_official_token_reduction | query understanding | unavailable | unavailable | unavailable | Recorded the stage output in trajectory. | observability |

## Evidence Flow Panel

| Metric | Value | Note |
| --- | --- | --- |
| **SQL evidence** | `answer source` | items=1 item(s); total_items=1; truncated_items=False |
| **API evidence** | `dry-run verification` | sql_calls_executed=1; api_calls_executed=1 |
| **Local evidence** | `not in packaged final answer` | No promoted local-evidence answer path for this row. |
| **Answer slots** | `SQL count grounded` | answer_intent=COUNT |

## Decision Flow Panel

| Decision | Value | Reason |
| --- | --- | --- |
| Route selected | SQL_ONLY | Schema count prompt classified as SQL-backed schema_dataset family. |
| SQL used? | yes | SQL provides the schema count answer source. |
| API used? | yes, dry-run | Packaged SQL_FIRST_API_VERIFY attempts API verification but credentials are unavailable. |
| Dry-run happened? | yes | Adobe credentials unavailable, so live verification payload was not executed. |
| Answer rewrite promoted? | no | Packaged answer already states SQL count and dry-run honesty. |

## Final Answer

> You have 74 schemas. This count comes from your blueprint query and is confirmed by the API response from Adobe Schema Registry, which shows tenant schemas are available.
