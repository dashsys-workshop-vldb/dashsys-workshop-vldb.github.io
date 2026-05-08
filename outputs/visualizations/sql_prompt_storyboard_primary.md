# SQL-Backed Primary Prompt Storyboard

`example_011` was chosen because it is SQL-backed in the packaged path: the prompt becomes validated SQL, SQL returns the answer count, and API verification is dry-run/unavailable.

## One Giant End-to-End Flowchart

```mermaid
flowchart TD
  classDef prompt fill:#e8f3ff,stroke:#2f6fad,stroke-width:1px,color:#102a43
  classDef interpret fill:#eef8ef,stroke:#3b873e,stroke-width:1px,color:#183b1b
  classDef plan fill:#fff7df,stroke:#b7791f,stroke-width:1px,color:#3d2a00
  classDef sql fill:#eafff7,stroke:#00856f,stroke-width:2px,color:#063b33
  classDef api fill:#f7f2ff,stroke:#805ad5,stroke-width:1px,color:#2d1b69,stroke-dasharray: 5 3
  classDef evidence fill:#f0fff4,stroke:#2f855a,stroke-width:1px,color:#1c4532
  classDef answer fill:#fff0f6,stroke:#b83280,stroke-width:2px,color:#521b41
  classDef output fill:#f7fafc,stroke:#4a5568,stroke-width:1px,color:#1a202c

  subgraph P["Input / Prompt Understanding"]
    P0["Raw user prompt<br/>How many schemas do I have?"]:::prompt
    P1["Prompt router interpretation<br/>confidence=0.84; reason=Local snapshot keyword(s) can be answered from DuckDB/par..."]:::prompt
    P2["Simple-prompt gate decision<br/>confidence=0.84; is_simple=False; suggested_action=USE_DATA_PIPELINE; reason=Local snap..."]:::prompt
    P3["Query normalization<br/>normalized: How many schemas do I have?<br/>matching text: how many schema do i have?"]:::prompt
    P4["Token/entity extraction<br/>domains=1 item(s)"]:::prompt
  end

  subgraph I["Query Interpretation"]
    I0["Query analysis<br/>route type: SQL_ONLY<br/>answer family: schema_dataset"]:::interpret
    I1["Lookup path / route intent<br/>api_mode=required"]:::interpret
  end

  subgraph C["Context + Planning"]
    C0["Context selection / metadata card<br/>estimated_metadata_tokens=451; prompt_tokens=1032; selected_apis=1 item(s); selected_card_name=sc..."]:::plan
    C1["SQL planning input<br/>selected_plan=generic_sql_first"]:::plan
    C2["Selected plan / strategy<br/>generic_sql_first<br/>SQL_FIRST_API_VERIFY"]:::plan
  end

  subgraph S["SQL Derivation"]
    S0["Prompt becomes SQL<br/>COUNT DISTINCT BLUEPRINTID FROM dim_blueprint"]:::sql
    S1["Generated SQL artifact<br/>SELECT COUNT(DISTINCT B.'BLUEPRINTID') AS blueprint_count FROM 'dim_blueprint' AS B"]:::sql
    S2["SQL validation<br/>api_validation_status=1 item(s); sql_validation_status=1 item(s)"]:::sql
    S3["SQLGlot AST validation<br/>destructive_sql_detected=False; parsed_ok=True; selected_columns=1 item(s); selected_ta..."]:::sql
    S4["SQL is the answer source<br/>API branch is dry-run verification only"]:::sql
  end

  subgraph X["Execution + Evidence"]
    X0["Tool execution<br/>SQL calls=1; API calls=1"]:::output
    X1["SQL execution result<br/>blueprint_count = 74"]:::sql
    X2["Dry-run API verification branch<br/>API verification attempted as dry-run; live API payload unavailable."]:::api
    X3["Evidence extraction / evidence bus<br/>evidence=1 field(s)"]:::evidence
  end

  subgraph A["Final Answer + Output"]
    A0["Answer slots / answer intent<br/>answer_intent=COUNT"]:::answer
    A1["Answer synthesis<br/>SQL count + dry-run verification note"]:::answer
    A2["Answer verification / reranking<br/>verifier_passed=True"]:::answer
    A3["Final answer<br/>You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable."]:::answer
    A4["Trajectory / checkpoint output<br/>strategy=SQL_FIRST_API_VERIFY; tools=2; tokens=751; runtime=0.008387499954551458"]:::output
  end

  P0 -->|"raw text captured"| P1
  P1 -->|"route policy applied"| P2
  P2 -->|"data pipeline selected"| P3
  P3 -->|"matching text derived"| P4
  P4 -->|"schema/count signals"| I0
  I0 -->|"route + family"| I1
  I1 -->|"schema path selected"| C0
  C0 -->|"compact metadata"| C1
  C1 -->|"planner chooses plan"| C2
  C2 -->|"SQL-first planning"| S0
  S0 -->|"SQL template filled"| S1
  S1 -->|"safety validation"| S2
  S2 -->|"AST extraction"| S3
  S3 -->|"safe to execute"| X0
  S4 -.->|"interpretation guard"| X1
  X0 -->|"DuckDB read-only query"| X1
  X0 -.->|"catalog-valid API verification"| X2
  X1 -->|"count evidence"| X3
  X2 -.->|"dry-run status"| X3
  X3 -->|"structured evidence"| A0
  A0 -->|"count intent"| A1
  A1 -->|"grounded claim check"| A2
  A2 -->|"verifier passed"| A3
  A3 -->|"logged outputs"| A4
```

**Takeaway:** SQL is the answer source (`blueprint_count = 74`). The API branch is shown because the packaged trace attempts verification, but it is dry-run/unavailable and does not provide the answer value.
