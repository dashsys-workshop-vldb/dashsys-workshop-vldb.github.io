# DASHSys Prompt-To-Answer Dataflow

## Quality Gate Facts

| Field | Value |
| --- | --- |
| Query ID | `example_031` |
| User query | Which files are available for download in batch 69de8a0e0cc6102b5d11f01e? |
| Strategy | `RAW_REAL_LLM_TWO_TOOLS_BASELINE` |
| Variant | Raw |
| Final answer preview | n/a - missing final answer |
| Tool call count | 0 |
| Runtime | 0.1249 |
| Estimated tokens | n/a - estimated_tokens missing |
| Checkpoint count | 0 |
| Candidate context mode | metadata_context_estimate_inferred |
| Context mode note | display-only inferred from context token estimate |

```mermaid
flowchart TD
  subgraph Input
    input_prompt["User Prompt<br/>Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?"]
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
    context["Context Mode<br/>metadata_context_estimate_inferred"]
    candidates["Context<br/>tables=none&lt;br/&gt;apis=none"]
    tokens -->|score relevance| context --> candidates
  end
  subgraph Planning
    planner["Planner<br/>RAW_REAL_LLM_TWO_TOOLS_BASELINE"]
    optimizer["Plan Optimizer<br/>selected=n/a - no optimizer selection recorded"]
    candidates -->|metadata + policy| planner --> optimizer
  end
  subgraph SQLPath["SQL Path"]
    sqlgen["SQL Generator<br/>source=none"]
    sqlval["SQL Validator<br/>n/a - no validation step recorded"]
    optimizer -->|SQL step if needed| sqlgen --> sqlval
  end
  subgraph APIPath["API Path"]
    apisel["API Selector<br/>endpoint=none"]
    apival["API Validator<br/>n/a - no validation step recorded<br/>dry_run=n/a - no API call in trajectory"]
    optimizer -->|API policy| apisel --> apival
  end
  subgraph ToolExecution["Tool Execution"]
    tools["Tool Calls<br/>sql=0 api=0<br/>invalid=0"]
    sqlval -->|execute_sql| tools
    apival -->|call_api / dry-run| tools
  end
  subgraph EvidenceBus
    evidence["EvidenceBus<br/>SQL evidence: n/a&lt;br/&gt;Live API evidence: n/a&lt;br/&gt;Dry-run API: n/a"]
    tools -->|extract facts| evidence
  end
  subgraph AnswerVerification["Answer Verification"]
    verifier["Verifier<br/>status=not_recorded"]
    evidence -->|answer slots + claims| verifier
  end
  subgraph FinalAnswer["Final Answer"]
    answer["Final Answer<br/>n/a - missing final answer"]
    verifier -->|safe answer| answer
  end
  subgraph Metrics
    metrics["Metrics<br/>tools=0<br/>tokens=n/a - estimated_tokens missing<br/>runtime=0.1249"]
    answer -->|record trajectory| metrics
  end
```

## SQL And API Preview

| Path | Preview | Validation | Result / Status |
| --- | --- | --- | --- |
| SQL | n/a - no SQL call in trajectory | n/a - no validation step recorded | row_count=n/a - no SQL row count recorded; rows=n/a - no SQL rows preview recorded |
| API | n/a - no API call in trajectory | n/a - no validation step recorded | dry_run=n/a - no API call in trajectory; live_api_evidence=n/a - no API call in trajectory; overall_evidence=False; preview=n/a - no API result preview recorded |

Context mode labels ending in `_inferred` are display-only summaries for the visualization; they are not recorded planner decisions.

## Tool Execution vs Evidence Availability

No successful evidence was available from executed tools.

| Metric | Value |
| --- | --- |
| execute_sql calls | 0 |
| call_api calls | 0 |
| valid tool calls | 0 |
| invalid tool calls | 0 |
| endpoint repairs | 0 |
| schema hint injections | 0 |
| SQL evidence available | n/a - no SQL call in trajectory |
| live API evidence available | n/a - no API call in trajectory |
| overall evidence available | False |
| dry-run only | n/a - no API call in trajectory |
| successful evidence count | 0 |
| zero-row uncertain | n/a - no SQL call in trajectory |

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

## SQL AST Validation

`n/a - SQL AST validation checkpoint inactive`

## Technique Impact Highlight

- Correctness: n/a - no checkpoint correctness role recorded
- Efficiency: n/a - no checkpoint efficiency role recorded
- Dataflow effect: n/a - no checkpoint effect recorded

## Prompt To SQL/API Mapping

```json
{
  "api": {
    "dry_run": "n/a - no API call in trajectory",
    "endpoint": "n/a - no API call in trajectory",
    "endpoint_repair": "n/a - no endpoint repair recorded",
    "live_evidence_available": "n/a - no API call in trajectory",
    "result_preview": "n/a - no API result preview recorded",
    "validation": "n/a - no validation step recorded"
  },
  "context": {
    "candidate_apis": "n/a - no candidate APIs recorded",
    "candidate_tables": "n/a - no candidate tables recorded",
    "confidence": "n/a - no candidate confidence recorded",
    "context_mode": "metadata_context_estimate_inferred",
    "context_mode_note": "display-only inferred from context token estimate",
    "estimated_context_tokens": 1338,
    "score_margin": "n/a - no candidate score margin recorded"
  },
  "evidence": {
    "dry_run_only": "n/a - no API call in trajectory",
    "evidence_available": false,
    "explanation": "No successful evidence was available from executed tools.",
    "live_api_evidence_available": "n/a - no API call in trajectory",
    "overall_evidence_available": false,
    "sql_evidence_available": "n/a - no SQL call in trajectory",
    "successful_evidence_count": 0,
    "zero_row_uncertain": "n/a - no SQL call in trajectory"
  },
  "normalization": {
    "normalized_query": "n/a - no normalization checkpoint recorded"
  },
  "prompt": "Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?",
  "route": {
    "api_policy": "n/a - no API policy recorded",
    "confidence": "n/a - no route confidence recorded",
    "mode": "n/a - no prompt router decision",
    "risk": "n/a - no route risk recorded"
  },
  "sql": {
    "preview": "n/a - no SQL call in trajectory",
    "result_preview": "n/a - no SQL rows preview recorded",
    "row_count": "n/a - no SQL row count recorded",
    "validation": "n/a - no validation step recorded"
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
