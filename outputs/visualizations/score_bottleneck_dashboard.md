# Score Bottleneck Dashboard

## How To Read This Page

1. Start from the score gap card.
2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.
3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.

## Primary Testing Prompt

> **example_031**
>
> # Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?
>
> Representative API-correct but answer-weak dry-run row: endpoint selection is correct, but live payload is unavailable.

## Score Gap Visual

```mermaid
flowchart LR
  A["Packaged 0.6491"] --> B["Best isolated 0.6558"]
  B --> C["Target 0.75"]
  A --> D["Submit-ready"]
  C --> E["Not winner-ready yet"]
  F["Main blockers"] --> G["Answer weakness"]
  F --> H["Dry-run payload missing"]
  F --> I["No accepted LLM candidates"]
  F --> J["Shadow/default-off not promotable"]
```

## Current Score Cards

| Metric | Value | Note |
| --- | --- | --- |
| **Packaged strict score** | `0.6491` | Current submit-ready package. |
| **Best isolated score** | `0.6558` | Safe progress, below target. |
| **Target** | `0.75` | Winner-readiness target in this score-push thread. |
| **example_031 API score** | `1.0` | Endpoint selection is correct. |
| **Answer score** | `0.1055` | example_031 final answer is weak. |
| **Main bottleneck** | `Dry-run API evidence lacks live payload, so files cannot be listed safely.` | Dry-run API evidence lacks live payload, so files cannot be listed safely. |

## Blocker Cards

| Metric | Value | Note |
| --- | --- | --- |
| **Answer-score bottleneck** | `example_031 API score=1.0, answer score=0.1055` | Dry-run API evidence lacks live payload, so files cannot be listed safely. |
| **Dry-run dependency** | `live credentials visible=False; dry-run rows=34` | The packaged path must not fabricate live API payload values. |
| **No accepted LLM candidates** | `accepted=0; candidates=6` | LLM rewrite search remains shadow-only and did not add a promoted candidate. |
| **Endpoint tie-break not promotable** | `trial eligible rows=0` | Tie-break v2 did not produce a safe positive trial set. |
| **Answer-shape v2 not promotable** | `recommendation=safe_for_answer_shape_v2_trial; projected=0.6497` | Answer-shape v2 remains default-off because gates did not justify promotion. |
| **Live credentials missing** | `credentials visible=False` | Live-readiness is diagnostic only and cannot change dry-run answers by itself. |

## Bottom Line

- The system is submit-ready because the packaged path is safe and readiness checks pass.
- It is not winner-ready because the packaged score remains below `0.75` and the remaining high-value fixes are blocked by evidence availability or promotion gates.
