# DASHSys End-to-End System Data Flow

```mermaid
flowchart LR
  subgraph S0["User Prompt Input"]
    user_prompt["User Prompt"]
  end
  subgraph S1["Runtime Config / Safety Preflight"]
    config_env["Config / env"]
    preflight["Safety preflight"]
    tool_contract["Tool contract<br/>execute_sql / call_api"]
  end
  subgraph S2["Prompt Routing"]
    prompt_router["Prompt Routing"]
    simple_gate["Simple Prompt Gate"]
    pipeline_decision{"Use data pipeline?"}
  end
  subgraph S3["Query Understanding"]
    normalization["Query Normalization"]
    tokens["Query Token Extraction"]
    query_router["Deterministic<br/>QueryRouter"]
    intent["Answer Intent"]
    analysis["QueryAnalysis"]
    semantic_enabled{"Semantic router<br/>enabled?"}
    llm_client["SDK LLMClient"]
    semantic_helper["LLM Semantic<br/>Routing Helper"]
    semantic_validation{"Hint validation"}
    semantic_status["shadow / not promoted"]
  end
  subgraph S4["Context Selection"]
    schema_index["SchemaIndex"]
    endpoint_catalog["EndpointCatalog"]
    relevance["Relevance scoring"]
    context_pack["Context packing"]
  end
  subgraph S5["Planning"]
    planner["SQL_FIRST_API_VERIFY<br/>packaged strategy"]
    evidence_policy{"Evidence policy"}
    call_budget["Tool-call budget"]
    plan_selection["Selected plan"]
  end
  subgraph S6["SQL Evidence Path"]
    sql_template["SQL template /<br/>generic SQL"]
    sql_validation{"SQL validation<br/>passed?"}
    sqlglot["SQLGlot AST<br/>validation"]
    duckdb["execute_sql<br/>DuckDB snapshot"]
    sql_result["SQL result"]
    sql_evidence["SQL evidence"]
  end
  subgraph S7["Adobe API Evidence Path"]
    api_plan["API plan"]
    api_catalog["Endpoint catalog<br/>validation"]
    api_validation{"API validation<br/>passed?"}
    headers["Credential/header<br/>construction"]
    call_api["call_api(method,<br/>url, params, headers)"]
  end
  subgraph S8["Live API / Dry-run Split"]
    credentials{"Adobe credentials<br/>present?"}
    live_api["Live API mode<br/>live readiness: warning"]
    dry_run["Dry-run fallback<br/>no credentials"]
    api_parser["API response<br/>parser"]
    evidence_state["evidence_state<br/>live_success / live_empty<br/>api_error / malformed<br/>dry_run_unavailable"]
    parsed_api["Parsed API<br/>evidence"]
  end
  subgraph S9["Mock Live API Readiness"]
    fixtures["Synthetic fixtures"]
    mock_parser["Mock live parser<br/>success: 126"]
    discovery["Discovery-chain<br/>readiness<br/>chains: 5"]
    mock_forward["EvidenceBus<br/>forwarding"]
    mock_slots["Answer slot<br/>verification"]
    diagnostic_only["diagnostic only"]
  end
  subgraph S10["EvidenceBus"]
    evidence_bus["EvidenceBus"]
    evidence_fields["ids / names / counts<br/>statuses / timestamps"]
    evidence_sources["SQL / live API /<br/>dry-run state"]
  end
  subgraph S11["Answer Slots"]
    answer_slots["Answer Slots"]
    slot_shape["COUNT / LIST<br/>STATUS / WHEN<br/>YES_NO"]
    slot_sources["source tracking"]
  end
  subgraph S12["Answer Synthesis"]
    answer_synthesis["Evidence-Aware<br/>Answer Synthesis"]
    templates["Evidence-aware<br/>templates"]
    faithfulness{"Claim Faithfulness<br/>Check"}
    rewrite_trial["Answer-only<br/>rewrite trial<br/>keep_trial_only"]
    rewrite_status["not promoted"]
    final_answer["Final Answer"]
  end
  subgraph S13["Trajectory Logging"]
    trajectory["Trajectory Logging"]
    metadata_json["metadata.json"]
    filled_prompt["filled_system_prompt.txt"]
    trajectory_json["trajectory.json"]
  end
  subgraph S14["Evaluation"]
    strict_eval["Strict Eval<br/>score: 0.6553"]
    hidden_eval["Hidden-style Eval<br/>48/48"]
    llm_baseline["LLM baseline eval<br/>diagnostic only"]
    readiness["check_submission_ready<br/>ready: True"]
  end
  subgraph S15["Final Submission / Reports"]
    final_package["final_submission<br/>packaging"]
    source_zip["source_code.zip"]
    workshop_audit["Workshop audit<br/>pass"]
    report_index["Consolidated<br/>report index"]
  end
  user_prompt --> config_env
  config_env --> preflight
  preflight --> tool_contract
  tool_contract --> prompt_router
  prompt_router --> simple_gate
  simple_gate --> pipeline_decision
  pipeline_decision -->|yes| normalization
  normalization --> tokens
  tokens --> query_router
  query_router --> intent
  intent --> analysis
  analysis --> schema_index
  analysis --> endpoint_catalog
  schema_index --> relevance
  endpoint_catalog --> relevance
  relevance --> context_pack
  context_pack --> planner
  planner --> evidence_policy
  evidence_policy --> call_budget
  call_budget --> plan_selection
  plan_selection -->|SQL branch| sql_template
  sql_template --> sql_validation
  sql_validation -->|yes| sqlglot
  sqlglot --> duckdb
  duckdb --> sql_result
  sql_result --> sql_evidence
  sql_evidence --> evidence_bus
  plan_selection -->|API branch| api_plan
  api_plan --> api_catalog
  api_catalog --> api_validation
  api_validation -->|yes| headers
  headers --> call_api
  call_api --> credentials
  credentials -->|yes| live_api
  credentials -->|no| dry_run
  live_api --> api_parser
  dry_run --> api_parser
  api_parser --> evidence_state
  evidence_state --> parsed_api
  parsed_api --> evidence_bus
  evidence_bus --> evidence_fields
  evidence_fields --> evidence_sources
  evidence_sources --> answer_slots
  answer_slots --> slot_shape
  slot_shape --> slot_sources
  slot_sources --> answer_synthesis
  answer_synthesis --> templates
  templates --> faithfulness
  faithfulness -->|supported| final_answer
  final_answer --> trajectory
  trajectory --> metadata_json
  trajectory --> filled_prompt
  trajectory --> trajectory_json
  trajectory_json --> final_package
  final_package --> source_zip
  final_package --> strict_eval
  final_package --> hidden_eval
  final_package --> readiness
  strict_eval -->|metrics| report_index
  hidden_eval -->|robustness| report_index
  readiness -->|ready| report_index
  workshop_audit -->|compliance| report_index
  analysis -.->|low confidence| semantic_enabled
  semantic_enabled -.->|feature flag| llm_client
  llm_client -.->|SDK only| semantic_helper
  semantic_helper -.->|JSON hint| semantic_validation
  semantic_validation -.->|valid| semantic_status
  semantic_status -.->|shadow only| relevance
  fixtures -.->|fixture data| mock_parser
  mock_parser -.->|mock| discovery
  discovery -.->|GET-only| mock_forward
  mock_forward -.->|parsed evidence| mock_slots
  mock_slots -.->|verified| diagnostic_only
  diagnostic_only -.->|readiness report| report_index
  faithfulness -.->|answer-only| rewrite_trial
  rewrite_trial -.->|strict gate| rewrite_status
  rewrite_status -.->|trial report| report_index
  trajectory -.->|baseline| llm_baseline
  llm_baseline -.->|diagnostic| report_index
  classDef answer fill:#d1fae5,stroke:#243044,color:#111827,stroke-width:1px;
  classDef api fill:#ffedd5,stroke:#243044,color:#111827,stroke-width:1px;
  classDef config fill:#e0f2fe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef context fill:#fef3c7,stroke:#243044,color:#111827,stroke-width:1px;
  classDef decision fill:#fee2e2,stroke:#243044,color:#111827,stroke-width:1px;
  classDef eval fill:#dbeafe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef evidence fill:#ccfbf1,stroke:#243044,color:#111827,stroke-width:1px;
  classDef final fill:#ddd6fe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef input fill:#dbeafe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef live fill:#fed7aa,stroke:#243044,color:#111827,stroke-width:1px;
  classDef muted fill:#f1f5f9,stroke:#243044,color:#111827,stroke-width:1px;
  classDef planning fill:#fde68a,stroke:#243044,color:#111827,stroke-width:1px;
  classDef routing fill:#ede9fe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef slots fill:#cffafe,stroke:#243044,color:#111827,stroke-width:1px;
  classDef sql fill:#dcfce7,stroke:#243044,color:#111827,stroke-width:1px;
  classDef trajectory fill:#e0e7ff,stroke:#243044,color:#111827,stroke-width:1px;
  classDef understanding fill:#f5e8ff,stroke:#243044,color:#111827,stroke-width:1px;
  class user_prompt input;
  class config_env config;
  class preflight config;
  class tool_contract config;
  class prompt_router routing;
  class simple_gate routing;
  class pipeline_decision decision;
  class normalization understanding;
  class tokens understanding;
  class query_router understanding;
  class intent understanding;
  class analysis understanding;
  class semantic_enabled decision;
  class llm_client muted;
  class semantic_helper muted;
  class semantic_validation decision;
  class semantic_status muted;
  class schema_index context;
  class endpoint_catalog context;
  class relevance context;
  class context_pack context;
  class planner planning;
  class evidence_policy decision;
  class call_budget planning;
  class plan_selection planning;
  class sql_template sql;
  class sql_validation decision;
  class sqlglot sql;
  class duckdb sql;
  class sql_result sql;
  class sql_evidence sql;
  class api_plan api;
  class api_catalog api;
  class api_validation decision;
  class headers api;
  class call_api api;
  class credentials decision;
  class live_api live;
  class dry_run live;
  class api_parser live;
  class evidence_state live;
  class parsed_api live;
  class fixtures muted;
  class mock_parser muted;
  class discovery muted;
  class mock_forward muted;
  class mock_slots muted;
  class diagnostic_only muted;
  class evidence_bus evidence;
  class evidence_fields evidence;
  class evidence_sources evidence;
  class answer_slots slots;
  class slot_shape slots;
  class slot_sources slots;
  class answer_synthesis answer;
  class templates answer;
  class faithfulness decision;
  class rewrite_trial muted;
  class rewrite_status muted;
  class final_answer answer;
  class trajectory trajectory;
  class metadata_json trajectory;
  class filled_prompt trajectory;
  class trajectory_json trajectory;
  class strict_eval eval;
  class hidden_eval eval;
  class llm_baseline muted;
  class readiness eval;
  class final_package final;
  class source_zip final;
  class workshop_audit final;
  class report_index final;
```

HTML artifact: `outputs/visualizations/end_to_end_system_dataflow.html`
