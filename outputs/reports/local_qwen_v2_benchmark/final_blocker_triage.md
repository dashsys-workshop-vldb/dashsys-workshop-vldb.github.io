# Final Blocker Triage

- generated_at_utc: `2026-06-02T14:49:54Z`
- provider: local OpenAI-compatible Qwen3.6-35B SDK-toolcall endpoint
- strategy under test: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- packaged default unchanged: `SQL_FIRST_API_VERIFY`
- strict dev eval run: `no`
- reason strict dev eval was not run: fresh V2 smoke did not pass the continuation gate

## Blockers Reviewed

| Blocker | Diagnosis | Fix status | Verification status |
|---|---|---|---|
| `example_003` timeout at `checkpoint_llm_owned_dependency_resolution` | Dependency resolution could enter LLM repair for impossible dependency values after a terminal dependency failure. | Added mechanical dependency precheck. Placeholder-dependent consumers now fail closed as `DEPENDENCY_FAILED`; order-only failed dependencies do not block SQL/API passes. | Unit regression passed. Strict eval not run because fresh smoke failed. |
| `example_012` missing audience-to-destination relation detail | Runtime evidence can contain ID bridge rows plus separate ID/name rows, but fallback facts did not expose the resolved relation. | Added cross-pass ID/name relation facts for true bridge rows. | Unit regression passed. Strict eval not run because fresh smoke failed. |
| `example_021` missing default merge-policy relation | Planner needed generic guidance to include relationship-bearing local fields for schema class / merge-policy relation prompts when available. | Added Semantic IR planner rule for relationship/default/schema-class/merge-policy prompts. Added fallback relation support when class/policy fields are present. | Unit regression passed. Strict eval not run because fresh smoke failed. |
| `example_004` evidence-selection risk | Final answer could list row IDs whose runtime status contradicted a requested status, e.g. failed prompt with enabled rows. | Added final semantic gate check for nonmatching requested-status rows. Inactive prompts allow non-active lifecycle values such as created/updated. | Unit regression passed; smoke mixed inactive row now passes. |

## Fresh Qwen Smoke

Fresh command:

```bash
DASHAGENT_LLM_PROVIDER=openai OPENAI_BASE_URL=http://localhost:8000/v1 OPENAI_MODEL=/Users/tanqinyang/hf-models/Qwen3.6-35B-A3B-OptiQ-4bit OPENAI_API_KEY=local-token LLM_TIMEOUT_SECONDS=180 HERMES_LLM_CALL_TIMEOUT_SEC=180 HERMES_SMOKE_PROMPT_TIMEOUT_SEC=120 .venv/bin/python scripts/run_hermes_v2_toolcall_smoke.py
```

Result summary from `outputs/reports/hermes_v2_toolcall_smoke/hermes_v2_toolcall_smoke.json`:

| Metric | Value |
|---|---:|
| row_count | 7 |
| passed_count | 6 |
| failed_count | 1 |
| timeout_count | 1 |
| unsupported_claims | 0 |
| no_tool_fp | 1 |
| final_semantic_gate_final_failures | 0 |
| runtime_fact_count | 7 |
| local_snapshot_fact_count | 7 |
| live_api_fact_count | 0 |
| sql_calls | 4 |
| api_calls | 0 |
| raw_sql_fallback_used_count | 0 |

Failing smoke row:

| prompt_id | failure | timed_out_stage | SQL | API | runtime facts | note |
|---|---|---|---:|---:|---:|---|
| `compare_local_live_birthday_status` | timeout | `checkpoint_llm_unified_planner_start` | 0 | 0 | 0 | Local Qwen planner exceeded the 120s per-prompt smoke timeout before producing a plan. |

Smoke improvement after fixes:

- `mixed_inactive_journeys` now passes.
- `no_tool_fp` remains caused only by the timed-out compare row report shape, not by an executed pure-direct bypass.
- No unsupported claims were introduced.
- No final semantic gate final failures remained in the final smoke.

## Strict Eval Decision

`scripts/run_dev_eval.py --strict --strategies ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` was not run because the fresh smoke did not satisfy:

- `passed_count=7`
- `unsupported_claims=0`
- `no_tool_fp=0`
- `final_semantic_gate_final_failures=0`

The current blocker before strict eval is the local Qwen planner timeout on the compare local/live smoke prompt.

## Validation

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | `1188 passed, 1 skipped` |
| `.venv/bin/python scripts/check_submission_ready.py` | `ok=true`; default strategy remains `SQL_FIRST_API_VERIFY`; query output count `73`; secret scan `ok=true` |
| `.venv/bin/python scripts/generate_sdk_usage_audit.py` | `runtime_llm_direct_http_hits=0` |
| `git diff --check` | passed |

## Recommendation

Safe to keep the narrow code changes for dependency fail-closed behavior, relation fact exposure, and requested-status grounding. Not safe to run or interpret strict V2 dev eval yet; first resolve the remaining local Qwen planner timeout for `compare_local_live_birthday_status`.
