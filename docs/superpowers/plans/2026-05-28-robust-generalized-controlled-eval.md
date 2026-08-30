# Robust Generalized Controlled Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit real-execution ablation modes for `ROBUST_GENERALIZED_HARNESS_CANDIDATE`, run organizer/internal/focused evaluations, and write diagnostic-only reports.

**Architecture:** Register ablation strategies as applied-trial aliases that keep `SQL_FIRST_API_VERIFY` as the execution base. Each ablation changes only explicit config flags, and all scoring reports preserve runtime isolation and score provenance.

**Tech Stack:** Python dataclasses/config flags, `AgentExecutor`, `EvalHarness`, internal 500 runner, pytest, JSON/Markdown reports.

---

### Task 1: Explicit Ablation Strategy Wiring

**Files:**
- Modify: `dashagent/config.py`
- Modify: `dashagent/planner.py`
- Modify: `dashagent/eval_harness.py`
- Modify: `scripts/run_dashagent_500_prompt_suite_eval.py`
- Test: `tests/test_organizer_applied_trial_strategies.py`

- [ ] Add explicit strategy names for the robust candidate and ablations.
- [ ] Add config helper mappings so each ablation toggles only its intended components.
- [ ] Add 500-runner real modes mapped to the same config helpers.
- [ ] Verify every ablation is `execution_base_strategy(...) == "SQL_FIRST_API_VERIFY"`.

### Task 2: Candidate Config Guards

**Files:**
- Modify: `dashagent/config.py`
- Modify: `dashagent/semantic_route_decision_ladder.py`
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] Add flags for semantic parse enablement and evidence-grounded final-answer verifier enablement.
- [ ] Let ablations disable semantic parse, safe API probe, staged policy, and LLM answer generation independently.
- [ ] Preserve packaged default behavior and final submission format.

### Task 3: Evaluation Report Driver

**Files:**
- Create: `scripts/run_robust_generalized_controlled_eval.py`
- Create reports under `outputs/reports/robust_generalized_*`
- Test: targeted script smoke or existing eval tests.

- [ ] Run preflight checks and write preflight JSON/MD.
- [ ] Run organizer 35 strict eval for baseline, full candidate, and ablations.
- [ ] Run internal 500 real eval for baseline, full candidate, and required ablations.
- [ ] Run focused stress subsets using real `AgentExecutor`.
- [ ] Analyze LLM answer verifier, component contribution, score provenance, and leakage/hardcode audits.
- [ ] Write the controlled eval summary without a promotion recommendation.

### Task 4: Validation

**Files:** validation/report artifacts only.

- [ ] Run hidden-style, submission readiness, workshop audit, SDK usage audit, pytest, and `git diff --check`.
- [ ] Run targeted secret scan over changed source, tests, reports, and eval outputs.
- [ ] Confirm packaged default remains `SQL_FIRST_API_VERIFY`.
