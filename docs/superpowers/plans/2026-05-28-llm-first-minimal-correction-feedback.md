# LLM-First Minimal Correction Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep LLM decisions primary for robust semantic routing, post-SQL API arbitration, and final-answer rewriting while using deterministic gates only for compact conflict feedback and execution safety.

**Architecture:** Add one shared `MinimalCorrectionFeedback` schema and use it in routing, post-SQL API decisions, and final-answer verification. Post-SQL gets a new LLM-first decision card/gate/verifier path for `ROBUST_GENERALIZED_HARNESS_CANDIDATE`, with risk-minimizing fallback only after one failed revision. Existing packaged `SQL_FIRST_API_VERIFY` remains unchanged.

**Tech Stack:** Python dataclasses, existing `LLMClient` abstraction, pytest, DASHSys `AgentExecutor`.

---

### Task 1: Shared Minimal Feedback Schema

**Files:**
- Create: `dashagent/minimal_correction_feedback.py`
- Test: `tests/test_post_sql_llm_first_decision.py`

- [ ] Write failing tests for compact feedback shape, narrowed allowed/forbidden outputs, and exclusion of raw rows/catalog/gold metadata.
- [ ] Implement `MinimalCorrectionFeedback`, `CorrectionConflict`, and helper builders.
- [ ] Run targeted tests.

### Task 2: LLM-First Semantic Routing Feedback

**Files:**
- Modify: `dashagent/routing_anti_hallucination_gate.py`
- Modify: `dashagent/semantic_route_decision_ladder.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Write failing tests proving semantic conflicts produce `checkpoint_minimal_correction_feedback_semantic`, revision result checkpoint, and no deterministic replacement decision.
- [ ] Change routing gate feedback to shared schema and record revision/fallback telemetry.
- [ ] Run targeted tests.

### Task 3: LLM-First Post-SQL API Decision

**Files:**
- Create: `dashagent/post_sql_semantic_decision_card.py`
- Create: `dashagent/post_sql_llm_decision.py`
- Create: `dashagent/post_sql_semantic_decision_gate.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_post_sql_llm_first_decision.py`

- [ ] Write failing post-SQL tests for valid local skip, invalid live/API skip, revision success, revision failure fallback, API_REQUIRED preservation, unresolved path blocking, and unsafe caveat.
- [ ] Implement card, LLM decision/revision, semantic gate, risk-minimizing fallback, and thin execution verifier.
- [ ] Integrate into robust candidate post-SQL checkpoints without changing packaged default.
- [ ] Run targeted tests.

### Task 4: Final Answer Minimal Rewrite Feedback

**Files:**
- Modify: `dashagent/evidence_grounded_final_answer_verifier.py`
- Test: `tests/test_evidence_grounded_final_answer_verifier.py`

- [ ] Write failing tests proving live-empty/global no-data and API-error/no-data failures receive compact rewrite feedback with only relevant facts.
- [ ] Replace broad rewrite feedback payload with shared minimal feedback payload and add checkpoint-friendly fields.
- [ ] Run targeted tests.

### Task 5: Report and Validation

**Files:**
- Create: `outputs/reports/minimal_correction_feedback_refactor.md`
- Create: `outputs/reports/minimal_correction_feedback_refactor.json`

- [ ] Run `python3 -m pytest -q tests/test_post_sql_llm_first_decision.py tests/test_evidence_grounded_final_answer_verifier.py tests/test_robust_generalized_candidate.py`.
- [ ] Run `python3 scripts/check_submission_ready.py`.
- [ ] Run `git diff --check`.
- [ ] Write implementation-only report with no promotion conclusion.
