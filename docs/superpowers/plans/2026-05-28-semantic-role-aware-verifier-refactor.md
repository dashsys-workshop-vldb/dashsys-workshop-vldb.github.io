# Semantic Role-Aware Verifier Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace keyword-style no-tool blocking in the robust candidate with a semantic-role-aware parse and consistency verifier.

**Architecture:** Add a `SemanticParse` layer between objective features and route action selection. The parser describes semantic roles; the verifier checks consistency between parse, objective spans, and `SemanticIntentDecision` without acting as a deterministic router.

**Tech Stack:** Python dataclasses, existing DashAgent semantic harness, pytest, JSON/Markdown diagnostics.

---

### Task 1: Semantic Parse Schema And Tests

**Files:**
- Create: `dashagent/semantic_parse.py`
- Create: `dashagent/semantic_parser.py`
- Create: `tests/test_semantic_parse_and_verifier.py`

- [ ] Write tests for conceptual list-format, inactive-journey definition, meta-language, real data retrieval, local count, out-of-domain, and keyword decoys.
- [ ] Verify the new tests fail because `dashagent.semantic_parse` and `dashagent.semantic_parser` do not exist.
- [ ] Implement `SemanticTarget`, `SemanticFilters`, `SemanticCapability`, and `SemanticParse` dataclasses with JSON-compatible `to_dict()`.
- [ ] Implement `parse_prompt_semantics()` with an LLM-ready interface and conservative deterministic fallback.
- [ ] Run the semantic parse tests and keep only schema/parser tests passing before verifier integration.

### Task 2: Objective Feature Span Additions

**Files:**
- Modify: `dashagent/prompt_semantic_ir.py`
- Test: `tests/test_semantic_parse_and_verifier.py`

- [ ] Add objective-only fields for quoted spans, meta-language indicators, operation candidate spans, target candidate spans, conceptual object terms, data object terms, and format request terms.
- [ ] Verify no route/no-tool/evidence decision fields are added to objective features.
- [ ] Run targeted tests proving “list” and domain words remain surface cues only.

### Task 3: Semantic Consistency Verifier

**Files:**
- Create: `dashagent/semantic_consistency_verifier.py`
- Test: `tests/test_semantic_parse_and_verifier.py`

- [ ] Implement `verify_semantic_consistency(features, semantic_parse, semantic_intent)` returning `ok`, `allow_no_tool`, `block_codes`, `consistency_codes`, and `fallback_action`.
- [ ] Allow no-tool for conceptual, meta-language, and out-of-domain parses with `evidence_need=NONE`.
- [ ] Block no-tool for supported data object, instance-level, data retrieval/count/status/date/relationship, requested fields, live/API state, explicit API-family, and objective/parse contradictions.
- [ ] Ensure blocking is not based on raw keyword alone.
- [ ] Run verifier tests.

### Task 4: Route Decision Ladder Integration

**Files:**
- Modify: `dashagent/semantic_route_decision_ladder.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Make the ladder build `SemanticParse`, validate it through the consistency verifier, and include both in checkpoints.
- [ ] Keep route actions limited to `LLM_DIRECT`, `LLM_SAFE_DIRECT`, `SAFE_API_PROBE`, and `EVIDENCE_PIPELINE`.
- [ ] Apply the new verifier only through the semantic harness/candidate path; do not change packaged default.
- [ ] Add `checkpoint_semantic_parse` and `checkpoint_semantic_consistency_verifier`.
- [ ] Run robust candidate tests.

### Task 5: Smoke And Report

**Files:**
- Create: `outputs/reports/semantic_role_aware_verifier_refactor.md`
- Create: `outputs/reports/semantic_role_aware_verifier_refactor.json`

- [ ] Run the required targeted pytest command.
- [ ] Run the two `run_one_query.py` smoke commands.
- [ ] Run `python3 scripts/check_submission_ready.py`.
- [ ] Run `git diff --check`.
- [ ] Write the report with no promotion recommendation and no benchmark conclusion.
