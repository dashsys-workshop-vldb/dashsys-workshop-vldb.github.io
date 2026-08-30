# Robust Generalized Harness Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `ROBUST_GENERALIZED_HARNESS_CANDIDATE` as an explicit non-default runtime strategy that exercises the full semantic routing, staged evidence, post-SQL policy, evidence quality, and answer grounding harness.

**Architecture:** The candidate reuses the existing `AgentExecutor` pipeline and maps to `SQL_FIRST_API_VERIFY` as its base strategy. Candidate-specific behavior is enabled only through strategy/config flags; packaged default, output schema, validators, and final submission artifacts remain unchanged.

**Tech Stack:** Python dataclasses, existing DashAgent executor/planner/eval harness, pytest, JSON/Markdown reports.

---

### Task 1: Strategy and Config Wiring

**Files:**
- Modify: `dashagent/planner.py`
- Modify: `dashagent/config.py`
- Modify: `dashagent/eval_harness.py`
- Modify: `scripts/run_dashagent_500_prompt_suite_eval.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Add `ROBUST_GENERALIZED_HARNESS_CANDIDATE` to explicit non-default strategy lists.
- [ ] Add config flags for safe API probe, evidence quality classifier, answer slot renderer, evidence-grounded answer builder, score provenance guard, runtime leakage guard, and hardcode/fake-score guard.
- [ ] Add `config_for_applied_trial_strategy(..., "ROBUST_GENERALIZED_HARNESS_CANDIDATE")` with all candidate flags enabled except the LLM advisor.
- [ ] Add the 500-runner real mode `robust_generalized_harness_candidate_real`.
- [ ] Test that strategy selection works and `PACKAGED_DEFAULT_STRATEGY` remains `SQL_FIRST_API_VERIFY`.

### Task 2: Runtime Candidate Guardrails

**Files:**
- Create: `dashagent/runtime_leakage_guard.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Implement a runtime guard that accepts only `query`, `query_id`, `strategy`, and candidate runtime facts; it rejects gold/category/tags/oracle/expected trace keys.
- [ ] Ensure no prompt-id or query-id-specific branch logic is introduced.
- [ ] Add score provenance checkpoint metadata for candidate runs without using score data at runtime.
- [ ] Test that prohibited runtime metadata raises in the guard and that normal candidate execution passes.

### Task 3: Candidate Semantic Routing Application

**Files:**
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Use the existing objective feature extractor, compact semantic context, classifier, anti-hallucination gate, no-tool verifier, and ladder checkpoints.
- [ ] Apply no-tool direct answers only when the ladder and safety verifier pass.
- [ ] Apply `SAFE_API_PROBE` only for one safe GET catalog endpoint with no unresolved path params.
- [ ] Fall back to the normal evidence pipeline for concrete or unsafe cases.
- [ ] Test conceptual no-tool, mixed prompt fallback, concrete data fallback, and safe API probe execution.

### Task 4: Staged Evidence and Post-SQL Policy

**Files:**
- Modify: `dashagent/executor.py`
- Reuse: `dashagent/staged_evidence_policy.py`
- Reuse: `dashagent/post_sql_deterministic_policy.py`
- Reuse: `dashagent/post_sql_api_call_verifier.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Record evidence match and initial branch policy checkpoints.
- [ ] For candidate mode, apply deterministic API skip/preserve decisions only after actual SQL results exist.
- [ ] Preserve API for API_REQUIRED, live/current/platform/status/API cues, explicit API-family cues, SQL partial with fillable API roles, SQL error with safe API candidate, and live/API zero-row cases.
- [ ] Skip API only when SQL is direct and complete and API is optional/no-gain.
- [ ] Test API_REQUIRED preservation, explicit schema registry preservation, SQL direct optional skip, and unresolved API blocking.

### Task 5: Evidence Quality Classifier

**Files:**
- Create: `dashagent/evidence_quality_classifier.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Classify SQL evidence as direct, partial, zero rows, error, or no useful fields.
- [ ] Classify API evidence as direct, verification-only, live empty, error, no usable payload, or not run.
- [ ] Classify SQL/API caveats and conflicts, keeping live empty scoped and API errors distinct from no-data.
- [ ] Add `checkpoint_evidence_quality_classifier`.
- [ ] Test SQL direct, SQL zero rows, API live empty, API error, and required API missing classes.

### Task 6: Evidence-Grounded Answer Builder

**Files:**
- Create: `dashagent/answer_slot_renderer.py`
- Create: `dashagent/evidence_grounded_answer_builder.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Render counts, lists, statuses, dates, relationships, live API evidence, local SQL evidence, and mixed concept/evidence answers from `AnswerSlots`.
- [ ] Avoid inventing missing roles and use distinct caveats for live empty, API error, and SQL local empty.
- [ ] Add `checkpoint_answer_slot_renderer` and `checkpoint_evidence_grounded_answer_builder`.
- [ ] Test count/status/date/list rendering and unsupported-claim-safe caveats.

### Task 7: Reports and Minimal Validation

**Files:**
- Create: `outputs/reports/robust_generalized_candidate_implementation.md`
- Create: `outputs/reports/robust_generalized_candidate_implementation.json`

- [ ] Run targeted pytest for candidate, applied trial, and staged evidence tests.
- [ ] Run `python3 scripts/check_submission_ready.py`.
- [ ] Run `git diff --check`.
- [ ] Write the implementation report with components, disabled pieces, selection instructions, tests, and known TODOs.
- [ ] Do not run a promotion gate or flip the packaged default.
