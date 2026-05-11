# Technique Visual Cards

## How To Read This Page

1. Start from the technique status badges.
2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.
3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.

Each card separates **status** from **runtime path** so experimental work is not confused with the packaged system.

## 🟢 promoted_default query_normalizer

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `raw query` | Data consumed by the technique. |
| **Changed artifact** | `query understanding` | Intermediate representation it changes. |
| **Output** | `normalized query and rewrite hints` | Data emitted downstream. |
| **Downstream effect** | `Canonicalizes user text before routing and retrieval.` | Why the technique exists. |
| **Affects** | `observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Deterministic preprocessing; retained as core routing support.

## 🟢 promoted_default query_tokens

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `normalized query` | Data consumed by the technique. |
| **Changed artifact** | `query understanding` | Intermediate representation it changes. |
| **Output** | `tokens and quoted entities` | Data emitted downstream. |
| **Downstream effect** | `Extracts tokens, quoted entities, and intent words for downstream ranking.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Low-cost deterministic signal used by ranking and templates.

## 🟢 promoted_default relevance_scorer

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `tokens, schema metadata, endpoint metadata` | Data consumed by the technique. |
| **Changed artifact** | `candidate ranking` | Intermediate representation it changes. |
| **Output** | `candidate relevance scores` | Data emitted downstream. |
| **Downstream effect** | `Ranks schema/API candidates using query-token overlap and metadata relevance.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core ranking signal; effects are embedded in current packaged metrics.

## 🟢 promoted_default plan_ensemble

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `candidate plans` | Data consumed by the technique. |
| **Changed artifact** | `planning` | Intermediate representation it changes. |
| **Output** | `one selected plan` | Data emitted downstream. |
| **Downstream effect** | `Deduplicates and selects a single plan from deterministic planning candidates.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Preserves deterministic single-plan execution.

## 🟢 promoted_default metadata_selector

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `candidate tables, APIs, context cards` | Data consumed by the technique. |
| **Changed artifact** | `context selection` | Intermediate representation it changes. |
| **Output** | `metadata.json and filled system prompt context` | Data emitted downstream. |
| **Downstream effect** | `Builds compact per-query metadata/context for planning.` | Why the technique exists. |
| **Affects** | `efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Needed to keep prompt context compact and deterministic.

## 🟢 promoted_default query_analysis

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `query tokens and schema/API hints` | Data consumed by the technique. |
| **Changed artifact** | `query analysis` | Intermediate representation it changes. |
| **Output** | `route_type, domain_type, answer intent` | Data emitted downstream. |
| **Downstream effect** | `Classifies route type, answer shape, and domain family.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core deterministic intent layer.

## 🟢 promoted_default prompt_router

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `raw query` | Data consumed by the technique. |
| **Changed artifact** | `routing` | Intermediate representation it changes. |
| **Output** | `route policy and requires_api decision` | Data emitted downstream. |
| **Downstream effect** | `Fast prompt-level route gate for SQL/API need and risk.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Promoted as routing safety layer.

## 🟢 promoted_default SQL_FIRST_API_VERIFY

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `metadata/context and route policy` | Data consumed by the technique. |
| **Changed artifact** | `strategy` | Intermediate representation it changes. |
| **Output** | `SQL/API execution plan` | Data emitted downstream. |
| **Downstream effect** | `Grounds with local SQL first, then verifies with API where needed.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `answer_score_delta=0.3199, api_score_delta=0.9791, correctness_delta=0.0, runtime_delta=0.0157, sql_score_delta=0.9333, strict_score_delta=0.0, token_delta=834.6, tool_call_delt...` | Unavailable means no source report measured a delta. |

**Why this status:** Best current strict score and correctness among packaged strategies.

## 🟢 promoted_default SQL templates

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `schema metadata and query analysis` | Data consumed by the technique. |
| **Changed artifact** | `SQL planning` | Intermediate representation it changes. |
| **Output** | `read-only SQL` | Data emitted downstream. |
| **Downstream effect** | `Generate validated SQL for recurring local-data query families.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Reusable templates are part of current SQL score.

## 🟢 promoted_default API templates

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `endpoint catalog, route policy, grounded IDs` | Data consumed by the technique. |
| **Changed artifact** | `API planning` | Intermediate representation it changes. |
| **Output** | `method/path/params` | Data emitted downstream. |
| **Downstream effect** | `Generate endpoint-catalog-valid API calls.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Reusable endpoint templates drive current API score.

## 🟢 promoted_default planner

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `route, metadata, templates` | Data consumed by the technique. |
| **Changed artifact** | `planning` | Intermediate representation it changes. |
| **Output** | `candidate plan` | Data emitted downstream. |
| **Downstream effect** | `Builds constrained SQL/API steps from route and context.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core packaged execution path.

## 🟢 promoted_default executor

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `selected plan` | Data consumed by the technique. |
| **Changed artifact** | `execution` | Intermediate representation it changes. |
| **Output** | `tool results, evidence, trajectory` | Data emitted downstream. |
| **Downstream effect** | `Runs validated SQL/API calls and records trajectory evidence.` | Why the technique exists. |
| **Affects** | `accuracy, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Required packaged runtime component.

## 🟢 promoted_default endpoint catalog

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `endpoint templates and planned API calls` | Data consumed by the technique. |
| **Changed artifact** | `API validation` | Intermediate representation it changes. |
| **Output** | `catalog validation result` | Data emitted downstream. |
| **Downstream effect** | `Defines allowed Adobe API endpoints and validation metadata.` | Why the technique exists. |
| **Affects** | `accuracy, safety` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Safety boundary for API calls.

## 🟢 promoted_default endpoint family ranker

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `query tokens and endpoint metadata` | Data consumed by the technique. |
| **Changed artifact** | `endpoint ranking` | Intermediate representation it changes. |
| **Output** | `ranked endpoint families` | Data emitted downstream. |
| **Downstream effect** | `Ranks endpoint families from reusable intent features.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Ranking is used; broader tie-break changes were not promoted.

## 🟡 shadow_only endpoint-schema rule candidates

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `query vocabulary, catalog metadata, path shapes` | Data consumed by the technique. |
| **Changed artifact** | `endpoint/schema routing` | Intermediate representation it changes. |
| **Output** | `candidate reranking diagnostics` | Data emitted downstream. |
| **Downstream effect** | `Shadow-tests reusable endpoint/schema routing rules.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `correctness_delta=0.0, runtime_delta=0.0, strict_score_delta=0.0, token_delta=0.0, tool_call_delta=0.0` | Unavailable means no source report measured a delta. |

**Why this status:** Kept shadow-only because measurable improvement was false.

## 🟡 shadow_only candidate generation

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `query, schema metadata, endpoint catalog` | Data consumed by the technique. |
| **Changed artifact** | `candidate search` | Intermediate representation it changes. |
| **Output** | `candidate SQL/API/answer plans` | Data emitted downstream. |
| **Downstream effect** | `Generates deterministic alternative plans for isolated search.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** No broad runtime promotion; used for diagnostics/trials.

## 🟡 shadow_only execution-based candidate selector

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `candidate plans and strict offline scores` | Data consumed by the technique. |
| **Changed artifact** | `candidate search` | Intermediate representation it changes. |
| **Output** | `safe candidate bundle` | Data emitted downstream. |
| **Downstream effect** | `Scores isolated candidates and selects only safe improvements.` | Why the technique exists. |
| **Affects** | `accuracy, safety` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Kept isolated unless trial gates pass.

## ⚪ default_off answer-shape v2

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 isolated_trial` | Where this technique actually runs today. |
| **Input** | `baseline answer and evidence` | Data consumed by the technique. |
| **Changed artifact** | `answer synthesis` | Intermediate representation it changes. |
| **Output** | `candidate answer` | Data emitted downstream. |
| **Downstream effect** | `Tests concise answer-shape rewrites with row-level A/B diagnostics.` | Why the technique exists. |
| **Affects** | `accuracy, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `answer_score_delta=-0.1162, correctness_delta=0.0006, strict_score_delta=0.0006` | Unavailable means no source report measured a delta. |

**Why this status:** Not a packaged default; isolated trial was below 0.75 target.

## 🟡 shadow_only supportable answer rewriter

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `recorded evidence, endpoint params, dry-run labels` | Data consumed by the technique. |
| **Changed artifact** | `answer synthesis` | Intermediate representation it changes. |
| **Output** | `supportable answer candidates` | Data emitted downstream. |
| **Downstream effect** | `Creates evidence-cited dry-run-safe answer rewrites.` | Why the technique exists. |
| **Affects** | `accuracy, safety` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `strict_score_delta=0.0` | Unavailable means no source report measured a delta. |

**Why this status:** Safe rows feed isolated trials; not final promoted behavior.

## ⚪ default_off SQL-only API-skip guard

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 isolated_trial` | Where this technique actually runs today. |
| **Input** | `route policy, SQL evidence, strict diagnostics` | Data consumed by the technique. |
| **Changed artifact** | `pre-execution guard` | Intermediate representation it changes. |
| **Output** | `API_SKIP decision metadata` | Data emitted downstream. |
| **Downstream effect** | `Conservatively skips API only when SQL fully answers and API score is not needed.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Not promoted; conservative guard available behind flag only.

## 🟢 promoted_default official-token reduction

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `metadata and prompt context` | Data consumed by the technique. |
| **Changed artifact** | `context optimization` | Intermediate representation it changes. |
| **Output** | `reduced prompt/context tokens` | Data emitted downstream. |
| **Downstream effect** | `Reduces context/token cost while preserving packaged behavior.` | Why the technique exists. |
| **Affects** | `efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Promoted because strict score tied/improved safely with large token reduction.

## 🔵 diagnostic_only local knowledge index

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `DBSnapshot parquet data and schema metadata` | Data consumed by the technique. |
| **Changed artifact** | `evidence retrieval` | Intermediate representation it changes. |
| **Output** | `provenance-safe evidence objects` | Data emitted downstream. |
| **Downstream effect** | `Builds Parquet-derived evidence objects for grounding.` | Why the technique exists. |
| **Affects** | `observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `strict_score_delta=0.0` | Unavailable means no source report measured a delta. |

**Why this status:** Coverage exists, but score impact is currently 0.

## 🟢 promoted_default cache

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `schema and value retrieval keys` | Data consumed by the technique. |
| **Changed artifact** | `retrieval optimization` | Intermediate representation it changes. |
| **Output** | `cache hits or regenerated values` | Data emitted downstream. |
| **Downstream effect** | `Caches deterministic retrieval/index artifacts.` | Why the technique exists. |
| **Affects** | `efficiency, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Infrastructure; no standalone score claim.

## 🟢 promoted_default evidence_bus

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `tool results and local evidence` | Data consumed by the technique. |
| **Changed artifact** | `evidence collection` | Intermediate representation it changes. |
| **Output** | `structured evidence records` | Data emitted downstream. |
| **Downstream effect** | `Carries SQL/API/local evidence into answer synthesis.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Safety layer for supportable answers.

## 🟢 promoted_default context cards

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `schema/API metadata and query analysis` | Data consumed by the technique. |
| **Changed artifact** | `context selection` | Intermediate representation it changes. |
| **Output** | `context cards` | Data emitted downstream. |
| **Downstream effect** | `Summarizes schema/API/domain hints for compact prompts.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core compact context mechanism.

## 🟢 promoted_default fast paths

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `query analysis and schema/API hints` | Data consumed by the technique. |
| **Changed artifact** | `planning optimization` | Intermediate representation it changes. |
| **Output** | `fast-path plan or no-op` | Data emitted downstream. |
| **Downstream effect** | `Handles simple deterministic query families with low overhead.` | Why the technique exists. |
| **Affects** | `efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Efficiency-oriented infrastructure.

## 🟢 promoted_default call budget

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `planned steps and route policy` | Data consumed by the technique. |
| **Changed artifact** | `planning optimization` | Intermediate representation it changes. |
| **Output** | `call budget decision` | Data emitted downstream. |
| **Downstream effect** | `Limits SQL/API calls for efficiency and trajectory stability.` | Why the technique exists. |
| **Affects** | `accuracy, efficiency, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Keeps tool calls within packaged efficiency target.

## 🟢 promoted_default evidence policy

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `route, SQL results, API policy` | Data consumed by the technique. |
| **Changed artifact** | `evidence gating` | Intermediate representation it changes. |
| **Output** | `evidence sufficiency decision` | Data emitted downstream. |
| **Downstream effect** | `Decides when SQL/API evidence is sufficient or API is required.` | Why the technique exists. |
| **Affects** | `accuracy` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Promoted core safety/answerability gate.

## 🟢 promoted_default plan optimizer

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `planned steps` | Data consumed by the technique. |
| **Changed artifact** | `planning optimization` | Intermediate representation it changes. |
| **Output** | `optimized plan` | Data emitted downstream. |
| **Downstream effect** | `Deduplicates and budgets plan steps before execution.` | Why the technique exists. |
| **Affects** | `efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Efficiency and safety support for packaged strategy.

## ⚪ default_off compact context experiment

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 isolated_trial` | Where this technique actually runs today. |
| **Input** | `candidate context` | Data consumed by the technique. |
| **Changed artifact** | `context optimization` | Intermediate representation it changes. |
| **Output** | `compact candidate context` | Data emitted downstream. |
| **Downstream effect** | `Tests smaller context windows under strict gates.` | Why the technique exists. |
| **Affects** | `efficiency` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Not promoted under current safety constraints.

## 🟡 shadow_only shadow repair

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `current plan and repaired candidate` | Data consumed by the technique. |
| **Changed artifact** | `repair diagnostics` | Intermediate representation it changes. |
| **Output** | `shadow repair score comparison` | Data emitted downstream. |
| **Downstream effect** | `Evaluates repaired plans without enabling repair execution.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Not promoted because repaired candidates did not pass gates.

## 🟡 shadow_only AST-guided SQL candidate canary

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `candidate SQL` | Data consumed by the technique. |
| **Changed artifact** | `SQL candidate diagnostics` | Intermediate representation it changes. |
| **Output** | `AST validation/ranking diagnostics` | Data emitted downstream. |
| **Downstream effect** | `Tests AST quality as a tie-break for SQL candidates.` | Why the technique exists. |
| **Affects** | `accuracy, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `correctness_delta=0.0, runtime_delta=0.0, strict_score_delta=0.0, token_delta=0.0, tool_call_delta=0.0` | Unavailable means no source report measured a delta. |

**Why this status:** Kept shadow-only because no alternatives existed.

## 🟡 shadow_only endpoint-family tie-break v2

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `ranked and selected endpoint families` | Data consumed by the technique. |
| **Changed artifact** | `endpoint routing diagnostics` | Intermediate representation it changes. |
| **Output** | `divergence report` | Data emitted downstream. |
| **Downstream effect** | `Shadow-tests deterministic preference for high-confidence ranked endpoint family.` | Why the technique exists. |
| **Affects** | `accuracy, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `strict_score_delta=0` | Unavailable means no source report measured a delta. |

**Why this status:** Kept shadow-only because projected positive delta rows = 0.

## 🔵 diagnostic_only live-mode readiness diagnostics

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `environment credential visibility and trajectories` | Data consumed by the technique. |
| **Changed artifact** | `diagnostics` | Intermediate representation it changes. |
| **Output** | `live readiness report` | Data emitted downstream. |
| **Downstream effect** | `Reports whether real Adobe credentials and live API payload readiness exist.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Credential visibility is false, so this remains diagnostic.

## 🔵 diagnostic_only hidden-style eval

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `hidden-style cases` | Data consumed by the technique. |
| **Changed artifact** | `evaluation gate` | Intermediate representation it changes. |
| **Output** | `pass/fail and stability metrics` | Data emitted downstream. |
| **Downstream effect** | `Checks paraphrase/hidden-style routing robustness.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Prevents weakening schema/family routing robustness; current report passes 48/48.

## 🔵 diagnostic_only leakage / robustness checks

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `candidate triggers and reports` | Data consumed by the technique. |
| **Changed artifact** | `safety gate` | Intermediate representation it changes. |
| **Output** | `leakage pass/fail flags` | Data emitted downstream. |
| **Downstream effect** | `Rejects query-id, exact-query, gold-path, or answer-memorization behavior.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Required gate for all accuracy experiments.

## 🟢 promoted_default answer verifier

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `final answer and evidence` | Data consumed by the technique. |
| **Changed artifact** | `answer validation` | Intermediate representation it changes. |
| **Output** | `verification result` | Data emitted downstream. |
| **Downstream effect** | `Checks final answer support and consistency.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core answer safety check.

## 🟢 promoted_default answer reranker

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `candidate answers` | Data consumed by the technique. |
| **Changed artifact** | `answer synthesis` | Intermediate representation it changes. |
| **Output** | `selected answer` | Data emitted downstream. |
| **Downstream effect** | `Ranks candidate answer phrasings when alternatives are available.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Used as packaged answer-selection support.

## 🟢 promoted_default answer claims / slots / intent / diagnostics

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `query and answer evidence` | Data consumed by the technique. |
| **Changed artifact** | `answer analysis` | Intermediate representation it changes. |
| **Output** | `answer intent/slots/claims` | Data emitted downstream. |
| **Downstream effect** | `Extracts answer shape, requested facts, and diagnostic slots.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Supports evidence-bound answer generation.

## 🔵 diagnostic_only package readiness checks

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `final submission artifacts` | Data consumed by the technique. |
| **Changed artifact** | `packaging gate` | Intermediate representation it changes. |
| **Output** | `readiness result` | Data emitted downstream. |
| **Downstream effect** | `Verifies packaged outputs and final submission readiness.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Final readiness gate remains passing in winner report.

## 🔵 diagnostic_only secret scan

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🔵 diagnostic_report` | Where this technique actually runs today. |
| **Input** | `repo outputs and final submission` | Data consumed by the technique. |
| **Changed artifact** | `packaging gate` | Intermediate representation it changes. |
| **Output** | `no_secret_scan result` | Data emitted downstream. |
| **Downstream effect** | `Prevents credential leakage in packaged outputs/reports.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Required readiness gate.

## 🟢 promoted_default trajectory checkpoints

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `pipeline stage outputs` | Data consumed by the technique. |
| **Changed artifact** | `observability` | Intermediate representation it changes. |
| **Output** | `trajectory checkpoint list` | Data emitted downstream. |
| **Downstream effect** | `Records execution checkpoints for explainability and auditability.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Core observability surface used by these visualizations.

## 🟡 shadow_only OpenRouter LLM rewrite search

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `baseline answer and local evidence registry` | Data consumed by the technique. |
| **Changed artifact** | `isolated candidate search` | Intermediate representation it changes. |
| **Output** | `candidate rewrites with claim citations` | Data emitted downstream. |
| **Downstream effect** | `Uses LLM proposals only for evidence-cited answer rewrites.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Kept shadow-only; safe rows = 0.

## 🟡 shadow_only supportable dry-run rewrite validation

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `candidate rewrites` | Data consumed by the technique. |
| **Changed artifact** | `answer candidate safety` | Intermediate representation it changes. |
| **Output** | `safe/unsafe rewrite labels` | Data emitted downstream. |
| **Downstream effect** | `Validates claim citations, dry-run unavailable wording, and SQL/API hash invariance.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `strict_score_delta=-0.0058` | Unavailable means no source report measured a delta. |

**Why this status:** Safe rows feed isolated trials only.

## 🟡 shadow_only autonomous packaged trials

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `safe candidate bundle` | Data consumed by the technique. |
| **Changed artifact** | `isolated trial` | Intermediate representation it changes. |
| **Output** | `best isolated score and gate results` | Data emitted downstream. |
| **Downstream effect** | `Runs isolated packaged-style trials over safe candidate bundles.` | Why the technique exists. |
| **Affects** | `accuracy, safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `correctness_delta=0.0067, runtime_delta=-0.001, strict_score_delta=0.0067, token_delta=-3.6571, tool_call_delta=0.0` | Unavailable means no source report measured a delta. |

**Why this status:** Best isolated score improved but target 0.75 was not reached.

## 🟢 promoted_default simple_prompt_gate

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟢 packaged` | Where this technique actually runs today. |
| **Input** | `raw prompt` | Data consumed by the technique. |
| **Changed artifact** | `prompt routing` | Intermediate representation it changes. |
| **Output** | `USE_DATA_PIPELINE or direct-answer decision` | Data emitted downstream. |
| **Downstream effect** | `Checkpointed gate that sends evidence questions into the backend pipeline.` | Why the technique exists. |
| **Affects** | `observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `unavailable` | Unavailable means no source report measured a delta. |

**Why this status:** Part of the packaged prompt routing path.

## 🟡 shadow_only SDK LLM baseline framework

| Metric | Value | Note |
| --- | --- | --- |
| **Runtime path** | `🟡 shadow_report` | Where this technique actually runs today. |
| **Input** | `dev prompts plus configured SDK backend metadata` | Data consumed by the technique. |
| **Changed artifact** | `shadow LLM baseline evaluation` | Intermediate representation it changes. |
| **Output** | `shadow baseline trajectories and strict comparison reports` | Data emitted downstream. |
| **Downstream effect** | `Provider-agnostic SDK baseline for OpenAI-compatible and Anthropic LLM comparisons.` | Why the technique exists. |
| **Affects** | `safety, observability` | Accuracy, efficiency, safety, or observability. |
| **Measured impact** | `strict_score=-0.0224, recommendation=keep_shadow_only` | Unavailable means no source report measured a delta. |

**Why this status:** Current SDK LLM baseline is a comparison framework; deterministic SQL_FIRST_API_VERIFY remains packaged.
