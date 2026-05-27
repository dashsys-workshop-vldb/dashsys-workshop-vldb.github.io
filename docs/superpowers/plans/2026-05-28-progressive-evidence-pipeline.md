# Progressive Evidence Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict `ROBUST_GENERALIZED_HARNESS_CANDIDATE` early semantic routing to safe exits and route all ambiguous/data-like prompts into progressive evidence acquisition.

**Architecture:** Add a focused `ProgressiveEvidencePolicy` module that consumes objective features, `SemanticParse`, `SemanticIntentDecision`, gate output, semantic consistency output, no-tool safety output, and safe probe candidates. `SemanticRouteDecisionLadder` remains the orchestration point, but its final action is filtered through the progressive policy so early routing can only no-tool safe conceptual/meta/out-of-domain prompts or perform a high-confidence single-endpoint safe API probe.

**Tech Stack:** Python dataclasses, existing DashAgent semantic routing modules, pytest.

---

### Task 1: Add Progressive Evidence Policy tests

**Files:**
- Modify: `tests/test_robust_generalized_candidate.py`
- Modify: `tests/test_semantic_parse_and_verifier.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:
- conceptual/meta prompts can still no-tool;
- supported data prompts enter `EVIDENCE_PIPELINE`;
- mixed conceptual+data prompts cannot no-tool;
- ambiguous API family prompts do not `SAFE_API_PROBE`;
- explicit safe API-only prompts can probe;
- API-required/live/status signals survive early routing.

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
python3 -m pytest -q tests/test_robust_generalized_candidate.py tests/test_semantic_parse_and_verifier.py
```

Expected: tests fail because `dashagent.progressive_evidence_policy` and `checkpoint_progressive_evidence_policy` do not exist yet.

### Task 2: Implement `dashagent/progressive_evidence_policy.py`

**Files:**
- Create: `dashagent/progressive_evidence_policy.py`
- Test: `tests/test_semantic_parse_and_verifier.py`

- [ ] **Step 1: Add dataclass and policy function**

Implement `ProgressiveEvidenceDecision` with:
- `entry_action`
- `confidence`
- `reason_codes`
- `risk_codes`
- `allowed_early_exit`
- `requires_evidence_pipeline`
- `safe_api_probe`
- `metrics`

Implement `decide_progressive_evidence_entry(...)` with hard no-tool and SAFE_API_PROBE restrictions from the user spec.

- [ ] **Step 2: Run focused policy tests**

```bash
python3 -m pytest -q tests/test_semantic_parse_and_verifier.py
```

Expected: progressive policy unit tests pass.

### Task 3: Refactor semantic ladder to use progressive policy

**Files:**
- Modify: `dashagent/semantic_route_decision_ladder.py`
- Test: `tests/test_semantic_parse_and_verifier.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] **Step 1: Wire policy after semantic/gate/verifier outputs**

Call `decide_progressive_evidence_entry(...)` before returning route actions. Add `checkpoint_progressive_evidence_policy` to the route decision checkpoints.

- [ ] **Step 2: Preserve safe exits only**

Ensure all non-safe early decisions become `EVIDENCE_PIPELINE`. Keep existing LLM semantic routing, revision feedback, and safe direct validation.

- [ ] **Step 3: Run targeted tests**

```bash
python3 -m pytest -q tests/test_robust_generalized_candidate.py tests/test_semantic_parse_and_verifier.py
```

Expected: tests pass.

### Task 4: Integrate checkpoint into executor and verify candidate smoke

**Files:**
- Modify: `dashagent/executor.py`
- Test: `tests/test_robust_generalized_candidate.py`

- [ ] **Step 1: Add executor checkpoint**

Emit `checkpoint_progressive_evidence_policy` alongside existing semantic route ladder checkpoints.

- [ ] **Step 2: Run candidate smoke tests**

Run the four `scripts/run_one_query.py` smoke commands from the user request.

### Task 5: Final validation and report

**Files:**
- Create: `outputs/reports/progressive_evidence_pipeline_refactor.md`
- Create: `outputs/reports/progressive_evidence_pipeline_refactor.json`

- [ ] **Step 1: Run validation**

```bash
python3 -m pytest -q tests/test_robust_generalized_candidate.py tests/test_semantic_parse_and_verifier.py tests/test_post_sql_llm_first_decision.py tests/test_evidence_grounded_final_answer_verifier.py
python3 scripts/check_submission_ready.py
git diff --check
```

- [ ] **Step 2: Secret/leakage scan**

Run targeted scans over changed source/tests/reports and verify no credential values or runtime hardcoding.

- [ ] **Step 3: Write report**

Record implemented behavior, smoke results, validation results, default strategy unchanged, and known TODOs. Do not include promotion recommendations or benchmark conclusions.

