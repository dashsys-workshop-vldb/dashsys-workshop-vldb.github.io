# Progressive Evidence Pipeline Refactor

## Scope

This implementation is restricted to `ROBUST_GENERALIZED_HARNESS_CANDIDATE`. It does not promote the candidate, does not change packaged/default strategy, and does not change final submission format.

## Implemented

- Added `dashagent/progressive_evidence_policy.py`.
- Added `ProgressiveEvidenceDecision` with:
  - `entry_action`
  - `confidence`
  - `reason_codes`
  - `risk_codes`
  - `allowed_early_exit`
  - `requires_evidence_pipeline`
  - `safe_api_probe`
  - `metrics`
- Refactored `SemanticRouteDecisionLadder` so early semantic routing is filtered through `ProgressiveEvidencePolicy`.
- Added `checkpoint_progressive_evidence_policy` to route decision checkpoints and executor checkpoints.
- Added an empty-answer guard to the evidence-grounded LLM answer generator. Empty generated answers now fall back to deterministic evidence-grounded rendering instead of passing claim verification due to having no claims.

## Early Routing Restrictions

Early routing can now exit only for:

- High-confidence conceptual/meta/out-of-domain prompts with:
  - `evidence_need=NONE`
  - `instance_level=false`
  - no requested data fields
  - no live/current/platform/API/status/family cue
  - semantic consistency verifier approval
- High-confidence API-only/live object prompts with:
  - supported data object grounding
  - API evidence need
  - low/unavailable SQL match
  - exactly one safe endpoint family
  - safe GET endpoint
  - no unresolved path params

All ambiguous or data-like prompts enter `EVIDENCE_PIPELINE`.

## Safety Guards

- No-tool is blocked for supported data objects, instance-level requests, data operations, requested fields, live/API cues, explicit API family cues, mixed conceptual+data prompts, status/date/entity filters, and ambiguous parses with concrete data signals.
- API-required/live/API-family evidence is preserved by early routing because these prompts enter the evidence pipeline instead of becoming no-tool or SQL-only.
- `SAFE_API_PROBE` is blocked for multiple competing API families, unresolved path params, conceptual/meta prompts, unsupported/out-of-domain prompts, SQL-applicable mixed prompts, and low-confidence endpoint family matches.
- Post-SQL LLM-first decision remains after SQL evidence exists, with the prior minimal correction feedback, risk-minimizing fallback, and thin execution verifier.
- Answer grounding remains EvidenceBus/AnswerSlots bounded; empty LLM answers fall back to deterministic evidence-grounded output.

## Smoke Results

| Query ID | Entry action | Evidence pipeline | Tool calls | Answer length |
| --- | --- | ---: | ---: | ---: |
| `progressive_concept_smoke` | `LLM_DIRECT` | `false` | `0` | `140` |
| `progressive_data_smoke` | `EVIDENCE_PIPELINE` | `true` | `2` | `367` |
| `progressive_live_count_smoke` | `EVIDENCE_PIPELINE` | `true` | `2` | `140` |
| `progressive_meta_smoke` | `LLM_DIRECT` | `false` | `0` | `120` |

## Validation

- `python3 -m pytest -q tests/test_robust_generalized_candidate.py tests/test_semantic_parse_and_verifier.py tests/test_post_sql_llm_first_decision.py tests/test_evidence_grounded_final_answer_verifier.py tests/test_evidence_grounded_llm_answer_generator.py`
  - Result: `62 passed in 9.21s`
- Smoke commands:
  - `python3 scripts/run_one_query.py "List three reasons why schemas matter." --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id progressive_concept_smoke`
  - `python3 scripts/run_one_query.py "Show inactive journeys." --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id progressive_data_smoke`
  - `python3 scripts/run_one_query.py "How many current schemas are in Adobe Experience Platform?" --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id progressive_live_count_smoke`
  - `python3 scripts/run_one_query.py "What does 'inactive journey' mean?" --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id progressive_meta_smoke`
- `python3 scripts/check_submission_ready.py`
  - Result: `ok=true`
  - Default strategy check: `SQL_FIRST_API_VERIFY`
  - Query output count: `73`
- `python3 scripts/audit_hardcoded_runtime_and_score_paths.py`
  - Unsafe runtime hardcodes: `0`
  - Unsafe fake-score hits: `0`
- Targeted secret scan over changed source/tests/reports
  - Result: clean
- `git diff --check`
  - Result: passed

## Default Strategy

Packaged/default strategy remains `SQL_FIRST_API_VERIFY`.

## Known TODOs

- Run controlled eval/ablation later; this pass intentionally made no promotion judgment.
- Track progressive policy metrics in full real-agent runs:
  - no-tool false positives
  - API-required underuse
  - SAFE_API_PROBE endpoint family mistakes
  - post-SQL feedback/revision/fallback counts
  - answer verifier block/rewrite/fallback counts
- Consider a dedicated first-evidence-source executor refactor if future eval shows current SQL-first planning is too rigid inside `EVIDENCE_PIPELINE`.
