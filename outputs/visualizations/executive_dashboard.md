# DASHSys Executive Visualization Dashboard

## How To Read This Page

1. Start from the raw prompt card.
2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.
3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.

## Primary Testing Prompt

> **example_031**
>
> # Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?
>
> Representative API-correct but answer-weak dry-run row: endpoint selection is correct, but live payload is unavailable.

## System At A Glance

```mermaid
flowchart LR
  A["Packaged system"] --> B["SQL_FIRST_API_VERIFY"]
  B --> C["Strict 0.6491"]
  C --> D["Submit-ready: True"]
  C --> E["Target 0.75"]
  F["Best isolated"] --> G["0.6558"]
  H["Main blocker"] --> I["Answer score 0.1055"]
  I --> J["Dry-run lacks live payload"]
```

| Metric | Value | Note |
| --- | --- | --- |
| **Packaged strict score** | `0.6491` | Current submit-ready score. |
| **Best isolated score** | `0.6558` | Safe trial progress, not promoted as winner-ready. |
| **Correctness** | `0.6743` | Must not regress. |
| **Hidden-style** | `48/48` | Current robustness gate. |
| **Final readiness** | `True` | Submission package still valid. |
| **Secret scan** | `True` | Readiness secret scan result. |

## Primary Prompt Journey

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

## Bottleneck Card

### 🔴 API-correct, answer-weak dry-run row

| Metric | Value | Note |
| --- | --- | --- |
| **API score** | `1.0` | Endpoint/method/params are correct. |
| **Answer score** | `0.1055` | Final wording cannot list files without live payload. |
| **Strict score** | `0.5346` | Row-level strict score for the packaged path. |
| **Main bottleneck** | `Dry-run API evidence lacks live payload, so files cannot be listed safely.` | The system stays honest instead of fabricating file names. |

## Technique State Legend

```mermaid
flowchart LR
  P["Packaged"] --> A["🟢 promoted_default"]
  S["Candidate reports"] --> B["🟡 shadow_only"]
  O["Feature flags"] --> C["⚪ default_off"]
  D["Reports/checks"] --> E["🔵 diagnostic_only"]
  X["Not promoted"] --> R["🔴 blocked/not_promoted"]
```

| Metric | Value | Note |
| --- | --- | --- |
| **Official-token reduction** | `🟢 promoted_default` | Enabled in the packaged path. |
| **Answer-shape v2** | `⚪ default_off` | Evaluated, not promoted. |
| **Endpoint tie-break v2** | `🟡 shadow_only` | Shadow-only report. |
| **Live readiness** | `🔵 diagnostic_only` | Diagnostic only; credentials not visible. |
| **Compact context** | `⚪ default_off` | Disabled/default-off. |
| **Repair execution** | `⚪ default_off` | Disabled/default-off. |

## Submit-Ready, Not Winner-Ready

- Submit-ready because packaging, hidden-style, readiness, and secret checks pass.
- Not winner-ready because packaged strict score remains below `0.75` and the best safe isolated score is still below target.
- The clearest visible blocker is answer quality on dry-run API rows where live payload values are unavailable.
