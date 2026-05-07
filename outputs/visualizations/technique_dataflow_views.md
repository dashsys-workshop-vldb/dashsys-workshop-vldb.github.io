# Technique Dataflow Views

Each view shows where a technique enters the pipeline, what representation it changes, and what downstream stage is affected.

## query_normalizer + query_tokens + relevance_scorer

```mermaid
flowchart LR
  A["Before: Raw query"] --> B["query_normalizer + query_tokens + relevance_scorer"]
  B --> C["After: normalized tokens + relevance features"]
  C --> D["Downstream: metadata selector"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | Raw query |
| Representation changed | normalized tokens + relevance features |
| Output produced | normalized tokens + relevance features |
| Downstream affected | metadata selector |
| Accuracy / efficiency / safety / observability | True / True / True / True |
| Before | Pipeline has Raw query. |
| After | Pipeline has normalized tokens + relevance features; downstream stage is metadata selector. |

## metadata_selector

```mermaid
flowchart LR
  A["Before: ranked schema/API candidates"] --> B["metadata_selector"]
  B --> C["After: compact metadata and context cards"]
  C --> D["Downstream: planner"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | ranked schema/API candidates |
| Representation changed | compact metadata and context cards |
| Output produced | compact metadata and context cards |
| Downstream affected | planner |
| Accuracy / efficiency / safety / observability | True / True / True / True |
| Before | Pipeline has ranked schema/API candidates. |
| After | Pipeline has compact metadata and context cards; downstream stage is planner. |

## SQL templates

```mermaid
flowchart LR
  A["Before: query analysis + schema metadata"] --> B["SQL templates"]
  B --> C["After: read-only SQL candidate"]
  C --> D["Downstream: SQL validator/executor"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | query analysis + schema metadata |
| Representation changed | read-only SQL candidate |
| Output produced | read-only SQL candidate |
| Downstream affected | SQL validator/executor |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has query analysis + schema metadata. |
| After | Pipeline has read-only SQL candidate; downstream stage is SQL validator/executor. |

## API templates

```mermaid
flowchart LR
  A["Before: endpoint intent + grounded params"] --> B["API templates"]
  B --> C["After: catalog-valid API call"]
  C --> D["Downstream: API validator/executor"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | endpoint intent + grounded params |
| Representation changed | catalog-valid API call |
| Output produced | catalog-valid API call |
| Downstream affected | API validator/executor |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has endpoint intent + grounded params. |
| After | Pipeline has catalog-valid API call; downstream stage is API validator/executor. |

## evidence_policy

```mermaid
flowchart LR
  A["Before: SQL/API results + route policy"] --> B["evidence_policy"]
  B --> C["After: evidence sufficiency decision"]
  C --> D["Downstream: answer synthesis"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | SQL/API results + route policy |
| Representation changed | evidence sufficiency decision |
| Output produced | evidence sufficiency decision |
| Downstream affected | answer synthesis |
| Accuracy / efficiency / safety / observability | True / True / True / True |
| Before | Pipeline has SQL/API results + route policy. |
| After | Pipeline has evidence sufficiency decision; downstream stage is answer synthesis. |

## supportable_answer_rewriter

```mermaid
flowchart LR
  A["Before: recorded evidence + dry-run labels"] --> B["supportable_answer_rewriter"]
  B --> C["After: evidence-cited answer candidate"]
  C --> D["Downstream: isolated trial only"]
```

| Field | Value |
| --- | --- |
| State | shadow_only |
| Input consumed | recorded evidence + dry-run labels |
| Representation changed | evidence-cited answer candidate |
| Output produced | evidence-cited answer candidate |
| Downstream affected | isolated trial only |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has recorded evidence + dry-run labels. |
| After | Pipeline has evidence-cited answer candidate; downstream stage is isolated trial only. |

## answer-shape v2

```mermaid
flowchart LR
  A["Before: baseline answer + evidence"] --> B["answer-shape v2"]
  B --> C["After: short shape-normalized candidate answer"]
  C --> D["Downstream: isolated A/B report"]
```

| Field | Value |
| --- | --- |
| State | default_off |
| Input consumed | baseline answer + evidence |
| Representation changed | short shape-normalized candidate answer |
| Output produced | short shape-normalized candidate answer |
| Downstream affected | isolated A/B report |
| Accuracy / efficiency / safety / observability | True / True / True / True |
| Before | Pipeline has baseline answer + evidence. |
| After | Pipeline has short shape-normalized candidate answer; downstream stage is isolated A/B report. |

## official-token reduction

```mermaid
flowchart LR
  A["Before: prompt/context metadata"] --> B["official-token reduction"]
  B --> C["After: reduced token prompt context"]
  C --> D["Downstream: packaged execution"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | prompt/context metadata |
| Representation changed | reduced token prompt context |
| Output produced | reduced token prompt context |
| Downstream affected | packaged execution |
| Accuracy / efficiency / safety / observability | False / True / True / True |
| Before | Pipeline has prompt/context metadata. |
| After | Pipeline has reduced token prompt context; downstream stage is packaged execution. |

## local_knowledge_index

```mermaid
flowchart LR
  A["Before: DBSnapshot parquet files"] --> B["local_knowledge_index"]
  B --> C["After: provenance-safe evidence objects"]
  C --> D["Downstream: answer/candidate diagnostics"]
```

| Field | Value |
| --- | --- |
| State | diagnostic_only |
| Input consumed | DBSnapshot parquet files |
| Representation changed | provenance-safe evidence objects |
| Output produced | provenance-safe evidence objects |
| Downstream affected | answer/candidate diagnostics |
| Accuracy / efficiency / safety / observability | True / True / True / True |
| Before | Pipeline has DBSnapshot parquet files. |
| After | Pipeline has provenance-safe evidence objects; downstream stage is answer/candidate diagnostics. |

## endpoint_family_ranker

```mermaid
flowchart LR
  A["Before: query intent + endpoint catalog"] --> B["endpoint_family_ranker"]
  B --> C["After: ranked endpoint family"]
  C --> D["Downstream: planner"]
```

| Field | Value |
| --- | --- |
| State | promoted_default |
| Input consumed | query intent + endpoint catalog |
| Representation changed | ranked endpoint family |
| Output produced | ranked endpoint family |
| Downstream affected | planner |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has query intent + endpoint catalog. |
| After | Pipeline has ranked endpoint family; downstream stage is planner. |

## endpoint-family tie-break v2

```mermaid
flowchart LR
  A["Before: ranked vs selected endpoint family"] --> B["endpoint-family tie-break v2"]
  B --> C["After: shadow divergence report"]
  C --> D["Downstream: isolated trial gate"]
```

| Field | Value |
| --- | --- |
| State | shadow_only |
| Input consumed | ranked vs selected endpoint family |
| Representation changed | shadow divergence report |
| Output produced | shadow divergence report |
| Downstream affected | isolated trial gate |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has ranked vs selected endpoint family. |
| After | Pipeline has shadow divergence report; downstream stage is isolated trial gate. |

## hidden-style eval

```mermaid
flowchart LR
  A["Before: paraphrase/hidden-style cases"] --> B["hidden-style eval"]
  B --> C["After: family/schema stability report"]
  C --> D["Downstream: promotion gate"]
```

| Field | Value |
| --- | --- |
| State | diagnostic_only |
| Input consumed | paraphrase/hidden-style cases |
| Representation changed | family/schema stability report |
| Output produced | family/schema stability report |
| Downstream affected | promotion gate |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has paraphrase/hidden-style cases. |
| After | Pipeline has family/schema stability report; downstream stage is promotion gate. |

## live-mode readiness

```mermaid
flowchart LR
  A["Before: credential visibility + dry-run rows"] --> B["live-mode readiness"]
  B --> C["After: live-readiness report"]
  C --> D["Downstream: human review"]
```

| Field | Value |
| --- | --- |
| State | diagnostic_only |
| Input consumed | credential visibility + dry-run rows |
| Representation changed | live-readiness report |
| Output produced | live-readiness report |
| Downstream affected | human review |
| Accuracy / efficiency / safety / observability | False / False / True / True |
| Before | Pipeline has credential visibility + dry-run rows. |
| After | Pipeline has live-readiness report; downstream stage is human review. |

## LLM answer rewrite search

```mermaid
flowchart LR
  A["Before: evidence registry + baseline answer"] --> B["LLM answer rewrite search"]
  B --> C["After: validated/rejected LLM rewrite candidates"]
  C --> D["Downstream: supportable rewrite gates"]
```

| Field | Value |
| --- | --- |
| State | shadow_only |
| Input consumed | evidence registry + baseline answer |
| Representation changed | validated/rejected LLM rewrite candidates |
| Output produced | validated/rejected LLM rewrite candidates |
| Downstream affected | supportable rewrite gates |
| Accuracy / efficiency / safety / observability | True / False / True / True |
| Before | Pipeline has evidence registry + baseline answer. |
| After | Pipeline has validated/rejected LLM rewrite candidates; downstream stage is supportable rewrite gates. |
