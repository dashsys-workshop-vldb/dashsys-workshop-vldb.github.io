# Evidence-Grounded Final Answer Verifier

## Scope

Implemented a flexible final-answer verifier for `ROBUST_GENERALIZED_HARNESS_CANDIDATE`.

Principle: free wording, bounded facts.

The packaged default remains `SQL_FIRST_API_VERIFY`. No promotion gate was run, and no final submission schema was changed.

## Components

- `dashagent/evidence_allowed_fact_index.py`
  - Builds normalized allowed facts from EvidenceGroundedAnswer/EvidenceGroundedAnswerCard-style payloads, AnswerSlots, EvidenceBus, and caveats.
  - Tracks counts, names, IDs, statuses, dates, relationships, scoped live-empty caveats, API-error caveats, and missing roles.
  - Drops gold/category/tags/oracle/expected-trace style fields from answer-card payloads.

- `dashagent/final_answer_claim_extractor.py`
  - Extracts hard factual claim candidates without treating every word as a claim.
  - Claim types include count, entity name, ID, status, date, relationship, existence, no-data, live-state/caveat, and soft text.

- `dashagent/final_answer_claim_matcher.py`
  - Deterministically matches claims against the allowed fact index.
  - Allows wording and format variation while blocking unsupported facts.
  - Keeps `LIVE_EMPTY` scoped and keeps `API_ERROR` distinct from no-data.

- `dashagent/ambiguous_claim_llm_judge.py`
  - Implements optional LLM judging for ambiguous claims only.
  - Default behavior is disabled/safe; backend unavailable returns `NEEDS_CAVEAT`.

- `dashagent/evidence_grounded_final_answer_verifier.py`
  - Runs fact indexing, extraction, matching, optional ambiguous judging, one rewrite attempt, and deterministic fallback.

- `dashagent/evidence_grounded_llm_answer_generator.py`
  - Allows candidate-only LLM answer wording.
  - Verifies generated wording before accepting.
  - Falls back to deterministic rendering when backend or verification fails.

## Candidate Integration

For `ROBUST_GENERALIZED_HARNESS_CANDIDATE`, the answer path now supports:

EvidenceBus -> AnswerSlots -> deterministic grounded answer -> optional LLM wording -> final-answer verifier -> one rewrite attempt -> deterministic fallback.

Added checkpoints:

- `checkpoint_final_answer_claim_extractor`
- `checkpoint_final_answer_claim_matcher`
- `checkpoint_evidence_grounded_final_answer_verifier`
- `checkpoint_llm_answer_rewrite_feedback`

## Validation

- `python3 -m pytest -q tests/test_evidence_grounded_final_answer_verifier.py tests/test_evidence_grounded_llm_answer_generator.py tests/test_robust_generalized_candidate.py`: `33 passed`
- `python3 scripts/check_submission_ready.py`: `ok=true`, default remains `SQL_FIRST_API_VERIFY`, embedded secret scan `ok=true`
- `git diff --check`: passed

## Known Limitations

- Entity-name extraction is intentionally conservative and should be tuned with broader runtime examples before any promotion review.
- The ambiguous-claim LLM judge is implemented but default-disabled.
- Candidate LLM answer generation safely falls back when backend or verification fails.
