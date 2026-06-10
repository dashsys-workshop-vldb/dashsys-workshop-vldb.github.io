# Minimal Correction Feedback Refactor

## Scope

This pass implemented the LLM-first semantic decision feedback flow for `ROBUST_GENERALIZED_HARNESS_CANDIDATE` only. It did not promote the candidate, did not change the packaged/default strategy, and did not change the final submission format.

## Implemented

- `dashagent/minimal_correction_feedback.py`
  - Shared compact feedback schema for semantic routing, post-SQL API decisions, and final-answer rewrites.
  - Sanitizes forbidden runtime/eval fields and strips large payload-style keys.
  - Provides compact token-estimate telemetry.

- LLM-first semantic routing feedback
  - `RoutingAntiHallucinationGate` now emits `MinimalCorrectionFeedback` instead of replacement route decisions.
  - `SemanticRouteDecisionLadder` records:
    - `checkpoint_minimal_correction_feedback_semantic`
    - `checkpoint_semantic_revision_result`
    - `checkpoint_semantic_fallback_if_any`
  - Semantic parse alignment is limited to low-authority fallback/invalid decisions, so the LLM remains the semantic decision maker when a valid decision is available.

- LLM-first post-SQL API decision
  - Added `dashagent/post_sql_semantic_decision_card.py`.
  - Added `dashagent/post_sql_llm_decision.py`.
  - Added `dashagent/post_sql_semantic_decision_gate.py`.
  - Candidate flow:
    - SQL result -> compact `PostSQLSemanticDecisionCard`
    - LLM decision `CALL_API|SKIP_API|CAVEAT_ONLY`
    - deterministic gate detects conflicts
    - minimal correction feedback is sent once
    - risk-minimizing fallback is used only if revision still fails or backend is unavailable
    - thin execution verifier enforces endpoint/safety contract

- Post-SQL gate boundaries
  - Gate detects conflicts such as `API_REQUIRED_CANNOT_SKIP`, `SQL_SCOPE_MISMATCH`, explicit API/live/status cues, SQL missing roles fillable by API, SQL errors, zero-row live/API needs, unsafe endpoints, and no-gain API calls.
  - Gate does not choose semantic intent, endpoint, SQL, API params, or final answer.

- Risk-minimizing fallback
  - Reports `RISK_MINIMIZING_FALLBACK`, `LOW_RISK_LOCAL_SQL_FALLBACK`, or `CAVEAT_UNSAFE_API_FALLBACK`.
  - Includes `semantic_certainty_claimed=false`.
  - Preserves API/evidence for high-risk cases and skips API only for low-risk local complete SQL cases.

- Thin execution verifier
  - Verifies executable contract only:
    - allowed candidate endpoint
    - safe GET
    - no unresolved path params
    - valid evidence gain or live/API need
  - Blocks unsafe/unmatched calls with `CAVEAT_ONLY` rather than fake no-data.

- Final-answer minimal correction feedback
  - `EvidenceGroundedFinalAnswerVerifier` now sends only blocked claims, issue codes, relevant allowed facts/caveats, allowed rewrite shape, and forbidden claim types.
  - It no longer resends the full allowed fact index in rewrite feedback.
  - Records:
    - `checkpoint_final_answer_minimal_correction_feedback`
    - `checkpoint_final_answer_rewrite_result`
    - `checkpoint_final_answer_fallback_if_any`

## Candidate Config

- `ROBUST_GENERALIZED_HARNESS_CANDIDATE` remains explicitly selectable.
- `enable_post_sql_llm_semantic_decision=true` only in the candidate config.
- Legacy post-SQL LLM advisor remains disabled in the candidate config.
- Default `Config.from_env()` keeps robust generalized candidate disabled and post-SQL LLM semantic decision disabled.

## Tests Run

- `python3 -m pytest -q tests/test_post_sql_llm_first_decision.py tests/test_evidence_grounded_final_answer_verifier.py tests/test_robust_generalized_candidate.py tests/test_semantic_routing_harness.py`
  - Result: `69 passed in 6.95s`
- `python3 scripts/check_submission_ready.py`
  - Result: `ok: true`
  - Default strategy check: `SQL_FIRST_API_VERIFY`
  - Query output count: `73`
- `python3 scripts/audit_hardcoded_runtime_and_score_paths.py`
  - Unsafe runtime hardcodes: `0`
  - Unsafe fake-score hits: `0`
- Targeted secret scan over changed source/tests
  - Result: clean
- `git diff --check`
  - Result: passed

## Default Strategy

Packaged/default strategy remains `SQL_FIRST_API_VERIFY`.

## Known TODOs

- Run the next controlled benchmark/ablation pass with a real configured LLM backend.
- Measure revision success/fallback rates on organizer 35 and internal 500 before any promotion discussion.
- Tune post-SQL card compactness if feedback token cost is high in real eval.
- Keep LLM answer generation and post-SQL LLM semantic decision candidate-scoped until future explicit promotion review.
