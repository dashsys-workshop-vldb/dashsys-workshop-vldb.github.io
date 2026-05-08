# Primary Prompt Storyboard: example_031

## How To Read This Page

1. Start from the raw prompt card.
2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.
3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.

## Primary Testing Prompt

> **example_031**
>
> # Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?
>
> Chosen because it shows the real submit-ready/not-winner-ready gap: API selection is correct, but dry-run answer evidence is incomplete.

## Bottleneck Snapshot

| Metric | Value | Note |
| --- | --- | --- |
| **API score** | `1.0` | The selected API call is scored as correct. |
| **Answer score** | `0.1055` | The final answer is weak because live file payload is unavailable. |
| **Main bottleneck** | `Dry-run API evidence lacks live payload, so files cannot be listed safely.` | No file list can be safely stated from dry-run evidence. |
| **Dry-run status** | `dry-run API evidence; live payload unavailable` | Credentials were not available for live API payloads. |

## Storyboard Flow

```mermaid
flowchart LR
  S0["Raw prompt"]
  S1["Prompt router view"]
  S0 --> S1
  S2["Simple-prompt gate"]
  S1 --> S2
  S3["Normalized query"]
  S2 --> S3
  S4["Tokens/entities/domains"]
  S3 --> S4
  S5["Query analysis"]
  S4 --> S5
  S6["Lookup path / route intent"]
  S5 --> S6
  S7["Context card"]
  S6 --> S7
  S8["Selected plan"]
  S7 --> S8
  S9["Evidence objects"]
  S8 --> S9
  S10["Answer slots / intent"]
  S9 --> S10
  S11["Verified final answer"]
  S10 --> S11
```

## Visual Step Cards

### ▣ 1. Raw prompt

**Payload:** Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?
**Technique:** `raw user query capture`
**What changed:** Original test prompt enters the packaged SQL_FIRST_API_VERIFY path.
**Primary impact:** observability

### ▣ 2. Prompt router view

**Payload:** confidence=0.9; reason=API/platform family keyword(s): batch, file, files.
**Technique:** `prompt_router`
**What changed:** Detects an API/platform batch-file request.
**Primary impact:** accuracy

### ▣ 3. Simple-prompt gate

**Payload:** confidence=0.9; is_simple=False; suggested_action=USE_DATA_PIPELINE; reason=API/platform family keyword(s): batch, file, files.
**Technique:** `simple_prompt_gate`
**What changed:** Sends the prompt into the evidence pipeline rather than a direct answer.
**Primary impact:** safety

### ▣ 4. Normalized query

**Payload:** normalized_query=Which files are available for download in batch 69de8a0e0...; matching_text=which file are available for download in batch 69de8a0e0c...
**Technique:** `query_normalizer`
**What changed:** Creates matching-friendly text while preserving original wording.
**Primary impact:** accuracy

### ▣ 5. Tokens/entities/domains

**Payload:** ids=1; domains=2 item(s)
**Technique:** `query_tokens`
**What changed:** Extracts batch/file intent and the batch id.
**Primary impact:** accuracy

### ▣ 6. Query analysis

**Payload:** strategy=SQL_FIRST_API_VERIFY; route_type=API_ONLY; domain_type=UNKNOWN; answer_family=batch
**Technique:** `query_analysis`
**What changed:** Classifies the route as API_ONLY and answer family as batch.
**Primary impact:** accuracy

### ▣ 7. Lookup path / route intent

**Payload:** api_mode=required
**Technique:** `lookup_path`
**What changed:** Narrows to batch API families and required id grounding.
**Primary impact:** accuracy

### ▣ 8. Context card

**Payload:** estimated_metadata_tokens=1000; prompt_tokens=1673; selected_apis=1 item(s); selected_card_name=batch
**Technique:** `metadata_selector + context_cards`
**What changed:** Packs the endpoint catalog/context into metadata and prompt budget.
**Primary impact:** efficiency

### ▣ 9. Selected plan

**Payload:** selected_plan=generic_sql_first
**Technique:** `planner + plan_ensemble`
**What changed:** Selects a one-call API plan before execution.
**Primary impact:** efficiency

### ▣ 10. Evidence objects

**Payload:** sql_calls_executed=0; api_calls_executed=1
**Technique:** `executor + evidence_bus`
**What changed:** Executes the catalog-valid API call in dry-run mode because credentials are unavailable.
**Primary impact:** safety

### ▣ 11. Answer slots / intent

**Payload:** answer_intent=LIST
**Technique:** `answer_slots`
**What changed:** Maps dry-run evidence into a LIST answer intent with missing payload slots.
**Primary impact:** accuracy

### ▣ 12. Verified final answer

**Payload:** verifier_passed=True
**Technique:** `answer_verifier + answer_reranker`
**What changed:** Keeps the honest dry-run answer instead of fabricating file names.
**Primary impact:** safety

## Final Answer

> Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.
