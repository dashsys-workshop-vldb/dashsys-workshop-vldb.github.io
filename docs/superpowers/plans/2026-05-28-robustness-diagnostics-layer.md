# Robustness Diagnostics Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add diagnostics-only reports that expose robustness, leakage, score provenance, routing, evidence policy, answer grounding, drift, and conversion risks without changing packaged runtime behavior.

**Architecture:** Reuse existing DashAgent execution artifacts and semantic/staged modules. Add small report scripts plus one shared score-provenance module; no script may promote a strategy or feed gold/category/tags/oracle data into runtime execution.

**Tech Stack:** Python standard library, existing `dashagent` modules, existing `scripts/run_dev_eval.py`, existing benchmark JSON/JSONL outputs, pytest.

---

### Task 1: Score Provenance And Hardcode Audit

**Files:**
- Create: `dashagent/score_provenance.py`
- Create: `scripts/audit_score_provenance.py`
- Create: `scripts/audit_hardcoded_runtime_and_score_paths.py`
- Test: `tests/test_robustness_diagnostics_layer.py`

- [ ] Add tests that simulated reports are promotion-ineligible and runtime input metadata is not permitted.
- [ ] Implement score provenance records for organizer strict, hidden-style, internal 500 heuristic, internal 500 organizer-style, and simulated trace.
- [ ] Implement a text audit that classifies runtime, eval-only, report-only, fixture, legacy simulated, and unsafe fake-score hits.
- [ ] Run targeted tests and verify JSON/MD reports are written.

### Task 2: Prompt And Semantic Diagnostics

**Files:**
- Create: `scripts/run_objective_prompt_feature_diagnostic.py`
- Create: `scripts/run_semantic_routing_diagnostic.py`
- Test: `tests/test_robustness_diagnostics_layer.py`

- [ ] Load organizer 35 and internal 500 prompts without passing gold to runtime.
- [ ] Extract objective prompt features and summarize cue/API-family/no-tool-risk coverage.
- [ ] Run the semantic route decision ladder in shadow/diagnostic mode and summarize actions, gate failures, revisions, no-tool decisions, and context cost.
- [ ] Verify diagnostics do not change packaged default.

### Task 3: Evidence And Answer Diagnostics

**Files:**
- Create: `scripts/run_staged_evidence_policy_diagnostic.py`
- Create: `scripts/run_answer_grounding_diagnostic.py`
- Test: `tests/test_robustness_diagnostics_layer.py`

- [ ] Inspect real trajectories and benchmark grades after execution only.
- [ ] Summarize SQL state, API-required preservation, optional skip candidates, blocked unresolved APIs, and possible API-underuse.
- [ ] Summarize answer grounding bottlenecks: missing facts, unsupported claims, live-empty/api-error wording, and evidence-available-but-not-rendered cases.
- [ ] Keep LLM advisor metrics separate and non-promoted.

### Task 4: Drift, Conversion, Dashboard, And Gate

**Files:**
- Create: `scripts/run_strict_baseline_drift_diagnostic.py`
- Create: `scripts/audit_500_organizer_style_conversion.py`
- Create: `scripts/generate_unified_robustness_diagnostics_dashboard.py`
- Create: `scripts/run_diagnostics_only_gate.py`
- Test: `tests/test_robustness_diagnostics_layer.py`

- [ ] Run strict SQL_FIRST twice and measure behavior versus runtime variance.
- [ ] Audit the 500 organizer-style conversion and document lost sidecar fields.
- [ ] Combine all diagnostics into one dashboard with score-source separation.
- [ ] Write a diagnostics-only gate that confirms no default change, no promotion, and validation readiness.
- [ ] Run the full validation command set and targeted secret scan.
