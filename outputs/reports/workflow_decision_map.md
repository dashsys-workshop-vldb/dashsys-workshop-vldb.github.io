# Workflow Decision Map

Diagnose decision stage first, run isolated variants, analyze helped/hurt examples, then decide without automatic promotion.

## Scope Controls

- Generated diagnostic prompts are coverage-only and cannot claim official strict-score improvement.
- Behavior-changing candidates remain isolated behind trial paths until later explicit promotion.
- Answer-only variants must preserve SQL/API/tool/evidence/dry-run hashes.

## Decision Stages

### 1. Prompt router

- Decision made: LLM_DIRECT vs LOCAL_DB_ONLY vs SQL_PLUS_API vs API_ONLY.
- Diagnostic question: Did this correctly decide whether the prompt needs SQL/API evidence?
- Input signals: query text, live/status/API keywords, data-object keywords
- Confidence/score: checkpoint_00_prompt_router.confidence when present
- Downstream effect: can keep conceptual prompts out of the data pipeline or send data questions to tools
- Possible improvement: calibrate with deterministic route confidence and relevance margins
- Safety risk: direct answers for evidence-needed prompts would be unsupported
- Improvement mode: `isolated_only`

Extended questions:
- Did router send data questions to evidence tools?
- Did it correctly avoid SQL/API for conceptual prompts?
- Did keyword routing miss synonyms?

### 2. Simple prompt gate

- Decision made: direct/simple handling vs USE_DATA_PIPELINE.
- Diagnostic question: Did it avoid direct answers for evidence-needed data questions?
- Input signals: prompt-router mode, confidence, requires_database, requires_api
- Confidence/score: checkpoint_simple_prompt_gate.confidence
- Downstream effect: prevents unsupported answers for data questions
- Possible improvement: tighten conceptual prompt definitions without weakening evidence routing
- Safety risk: unsupported claims if data prompts bypass tools
- Improvement mode: `isolated_only`

Extended questions:
- Does simple handling ever trigger for factual data questions?

### 3. Query normalization

- Decision made: rewrite/no rewrite, singular/plural normalization, synonym normalization.
- Diagnostic question: Did normalization preserve meaning while improving matchability?
- Input signals: raw query, known plural/domain terms
- Confidence/score: normalization rewrites list
- Downstream effect: feeds router, token extraction, and template matching
- Possible improvement: record before/after tokens and preserve quoted entities
- Safety risk: meaning drift
- Improvement mode: `promotable_if_hashes_safe`

Extended questions:
- Did singular/plural normalization help route matching without changing meaning?

### 4. Query token extraction

- Decision made: domain/status/date/id/entity extraction.
- Diagnostic question: Did it capture the important user intent signals?
- Input signals: normalized query, quoted entities, date/status patterns
- Confidence/score: token presence and value-retrieval matches
- Downstream effect: drives answer families and SQL/API filters
- Possible improvement: add typo-tolerant synonyms only when generalizable
- Safety risk: wrong entity/status filters
- Improvement mode: `isolated_only`

Extended questions:
- Were names, IDs, dates, status words, and entity words captured?

### 5. Deterministic QueryRouter

- Decision made: domain_type, route_type, confidence, candidate tables/APIs.
- Diagnostic question: Is router confidence calibrated against actual correctness?
- Input signals: matching text, domain keywords, candidate tables/APIs
- Confidence/score: route step confidence
- Downstream effect: seeds QueryAnalysis, context, and plan families
- Possible improvement: combine route confidence with relevance margin and template support
- Safety risk: misrouting can cause wrong tool path
- Improvement mode: `isolated_only`

Extended questions:
- Are low-confidence rows actually wrong, or just short prompts?
- Does confidence predict strict score?

### 6. QueryAnalysis

- Decision made: answer_family, SQL template, API templates, lookup path, API need decision.
- Diagnostic question: Did analysis choose the correct answer family and tool family?
- Input signals: route decision, tokens, schema/API relevance
- Confidence/score: analysis confidence when available
- Downstream effect: controls SQL/API template families and answer slots
- Possible improvement: audit answer-family alignment before changing templates
- Safety risk: wrong family can silently produce weak answers
- Improvement mode: `isolated_only`

Extended questions:
- Did the chosen answer family match COUNT/LIST/STATUS/DATE intent?

### 7. Relevance scoring

- Decision made: top tables, top APIs, top answer families, join hints.
- Diagnostic question: Did selected context include the true needed source?
- Input signals: tokens, schema summaries, endpoint labels
- Confidence/score: relevance compact/table/API lists
- Downstream effect: limits context and template candidates
- Possible improvement: log top-2 margin and compare selected context to executed SQL/API
- Safety risk: wrong table/API context
- Improvement mode: `isolated_only`

Extended questions:
- Were top-2 candidates close?
- Were wrong tables selected due to missing synonyms?

### 8. Metadata/context selection

- Decision made: selected tables, selected columns, selected APIs, compact/full context.
- Diagnostic question: Did context include enough evidence while avoiding token noise?
- Input signals: relevance, route, templates, value retrieval
- Confidence/score: metadata/prompt token counts
- Downstream effect: sets prompt and trajectory evidence surface
- Possible improvement: require template-required columns in selected context
- Safety risk: missing columns or too much noise
- Improvement mode: `isolated_only`

Extended questions:
- Did selected context include required columns?
- Did compact context hurt any query?

### 9. Plan generation

- Decision made: SQL_FIRST_API_VERIFY plan, SQL/API order, fast path/template/generic plan.
- Diagnostic question: Did the plan pick the right SQL/API path?
- Input signals: analysis, metadata, evidence policy
- Confidence/score: plan rationale and step families
- Downstream effect: determines executable tool calls
- Possible improvement: compare plan family to strict component failures
- Safety risk: invalid SQL/API if validators miss issues
- Improvement mode: `isolated_only`

Extended questions:
- Did losing candidates have better answer potential?

### 10. Plan ensemble selection

- Decision made: selected candidate, rejected candidates, candidate scores.
- Diagnostic question: Did the selected plan actually lead to better strict score?
- Input signals: candidate scores, tool-call estimates, validation signals
- Confidence/score: optimizer.plan_ensemble.candidate_scores
- Downstream effect: executes exactly one selected plan
- Possible improvement: add answer-shape/evidence completeness scoring in isolated trials
- Safety risk: executing multiple plans would violate cost assumptions
- Improvement mode: `isolated_only`

Extended questions:
- Are candidate scores aligned with strict score?

### 11. Evidence policy

- Decision made: API_REQUIRED, API_OPTIONAL, API_SKIP.
- Diagnostic question: Will API_REQUIRED/API_OPTIONAL calls produce useful live evidence when Adobe credentials are available, while dry-run remains an honest fallback?
- Input signals: route, analysis, credential/dry-run state
- Confidence/score: plan rationale evidence policy label
- Downstream effect: can add live API evidence in production or dry-run fallback labels locally
- Possible improvement: harden live API readiness, response parsing, and EvidenceBus API evidence flow before optimizing dry-run fallback wording
- Safety risk: skipping truly required API would lose future live evidence
- Improvement mode: `isolated_only`

Extended questions:
- Which queries truly need live API?
- Does dry-run fallback remain honest without weakening API_REQUIRED live behavior?

### 12. Tool-call budget

- Decision made: max SQL calls, max API calls, total tool limit.
- Diagnostic question: Are tool calls being spent where they improve correctness?
- Input signals: plan steps, call budget, optimizer actions
- Confidence/score: tool_call_count and budget settings
- Downstream effect: affects efficiency penalty and answer evidence
- Possible improvement: track API_REQUIRED vs API_OPTIONAL and live-readiness before changing budgets
- Safety risk: over-pruning useful evidence
- Improvement mode: `isolated_only`

Extended questions:
- Are extra API calls improving correctness?

### 13. SQL validation / AST validation

- Decision made: safe or blocked SQL, selected tables/columns, unknown table/column.
- Diagnostic question: Are validators blocking unsafe SQL while preserving valid useful SQL?
- Input signals: generated SQL, schema index, read-only checks
- Confidence/score: validation.ok/errors/warnings
- Downstream effect: prevents unsafe SQL execution
- Possible improvement: improve validators only by making valid/invalid separation clearer
- Safety risk: weakening validators is prohibited
- Improvement mode: `isolated_or_validator_safe_only`

Extended questions:
- Are validators blocking unsafe SQL while preserving valid useful SQL?

### 14. API validation

- Decision made: endpoint allowed or blocked, dry-run behavior.
- Diagnostic question: Are API calls valid and useful under missing live credentials?
- Input signals: endpoint catalog, method/url/params, credential availability
- Confidence/score: api validation ok/errors/warnings
- Downstream effect: permits catalog-safe Adobe API calls or dry-run records
- Possible improvement: endpoint-family trials only if strict and safety gates pass
- Safety risk: unsafe or fabricated API evidence
- Improvement mode: `isolated_only`

Extended questions:
- Which queries truly need live API?

### 15. Execution

- Decision made: SQL result and API result/dry-run result.
- Diagnostic question: Did execution produce useful evidence or just cost?
- Input signals: validated plan, local DB, Adobe credentials
- Confidence/score: result ok/row_count/dry_run
- Downstream effect: feeds EvidenceBus and final answer
- Possible improvement: live API response parser and EvidenceBus readiness; dry-run wording remains fallback polish
- Safety risk: fabricated live API evidence is prohibited
- Improvement mode: `answer_only_or_isolated`

Extended questions:
- Did SQL/API results contain enough evidence to answer directly?

### 16. EvidenceBus

- Decision made: forwarded SQL/API facts, IDs/names/counts/timestamps/statuses.
- Diagnostic question: Did the right evidence reach answer synthesis?
- Input signals: tool results, answer slots, evidence extraction
- Confidence/score: slots_present and unsupported_claims_count
- Downstream effect: controls grounded claims in final answer
- Possible improvement: answer-only rewrites with unchanged SQL/API/evidence hashes
- Safety risk: unsupported claims
- Improvement mode: `answer_only_isolated`

Extended questions:
- Were IDs, names, counts, statuses, and dates forwarded?

### 17. Answer slots

- Decision made: answer intent and count/list/status/date/yes-no shape.
- Diagnostic question: Did slots correctly represent the user’s requested answer type?
- Input signals: answer diagnostics, tool facts, query intent
- Confidence/score: answer_diagnostics slots_present
- Downstream effect: affects answer template and shape
- Possible improvement: COUNT/LIST/STATUS/WHEN template trials
- Safety risk: shape fixes must preserve evidence hashes
- Improvement mode: `answer_only_isolated`

Extended questions:
- Does the slot shape match COUNT/LIST/STATUS/DATE intent?

### 18. Answer synthesis

- Decision made: final answer wording and dry-run caveat.
- Diagnostic question: Does the answer directly answer the prompt using evidence?
- Input signals: EvidenceBus facts, answer slots, dry-run label
- Confidence/score: strict answer score
- Downstream effect: dominant current correctness bottleneck
- Possible improvement: answer-only rewrite variants preserving SQL/API/tool/evidence/dry-run hashes
- Safety risk: unsupported answer claims
- Improvement mode: `answer_only_isolated`

Extended questions:
- Is the answer too vague?
- Does it mention dry-run unnecessarily?

### 19. Answer verification/reranking

- Decision made: supported claims, unsupported claims, selected answer candidate.
- Diagnostic question: Is verifier checking groundedness and answer shape, not just literal support?
- Input signals: answer diagnostics, unsupported claim counts
- Confidence/score: verifier_passed and unsupported_claims_count
- Downstream effect: should prefer grounded and correctly shaped answers
- Possible improvement: shape-aware verifier scoring in isolated answer-only trials
- Safety risk: rejecting good answers or accepting weak unsupported ones
- Improvement mode: `answer_only_isolated`

Extended questions:
- Are weak answers passing because claims are supported but badly worded?

### 20. Token reduction / packaging

- Decision made: fields reduced, packaged trajectory unchanged enough for reproducibility.
- Diagnostic question: Did token reduction preserve reproducibility and correctness?
- Input signals: packaging policy, trajectory manifest, readiness checks
- Confidence/score: check_submission_ready and manifest checks
- Downstream effect: submission size and reproducibility
- Possible improvement: report-only checks unless readiness proves safe
- Safety risk: final submission contamination or irreproducible trajectories
- Improvement mode: `promotable_only_with_readiness_pass`

Extended questions:
- Did packaged trajectory still preserve original query, tools, answer, tokens, and runtime?
