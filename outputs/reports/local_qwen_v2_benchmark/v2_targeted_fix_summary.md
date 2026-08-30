# V2 Targeted Fix Summary: Local Qwen SDK-Toolcall Path

## Files Changed
Runtime/script:
- `dashagent/v2_semantic_ir_context.py`
- `dashagent/v2_semantic_ir_planner.py`
- `dashagent/final_answer_claim_extractor.py`
- `dashagent/llm_final_answer_composer.py`
- `scripts/run_hermes_v2_toolcall_smoke.py`

Tests:
- `tests/test_v2_semantic_ir.py`
- `tests/test_llm_final_answer_composer.py`
- `tests/test_hermes_v2_toolcall_smoke.py`

## Fixes Applied
- Added mechanical field hints for primary name fields, label fields, and entity lookup fields.
- Added one SDK toolcall retry before atomic fallback when the model omits `submit_semantic_ir_plan`.
- Tightened planner instructions for local schema ownership, local inactive journeys, quoted entity name filters, and explicit API/live source cues.
- Hardened count-claim extraction for percentages and leading-zero entity-code-like values.
- Hardened fallback answer summaries so local evidence survives partial API/concept failure and broad summaries pass the final semantic gate.
- Fixed smoke runner queue handling after child-process exit to avoid false `prompt_worker_returned_no_result` rows.

## What Stayed Unchanged
- Packaged default remains `SQL_FIRST_API_VERIFY`.
- V2 remains explicit/shadow only.
- No Pioneer or Gemini run was used.
- No backend semantic planner, free-form SQL/API primary path, or hidden/gold wording optimization was added.

## Validation Results
| Command | Result |
|---|---|
| `python3 scripts/probe_hermes_sdk_toolcall.py` with local Qwen env | passed, native SDK tool calls supported |
| `python3 scripts/run_hermes_v2_toolcall_smoke.py` with local Qwen env | passed 7/7, 0 timeouts, 0 unsupported claims, 0 no_tool_fp, 0 final semantic gate final failures |
| `python3 scripts/run_dev_eval.py --strict --strategies ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 --per-query-timeout-sec 240` | completed 35 rows, 1 timeout: `example_003` |
| `python3 scripts/run_dev_eval.py --strict --strategies SQL_FIRST_API_VERIFY --per-query-timeout-sec 240` | completed 35 rows, 0 timeouts |
| `python3 scripts/run_semantic_route_promotion_gate.py` | promotion_allowed=false, recommendation=`keep_shadow_only` |
| `python3 scripts/run_integrated_robustness_gate.py` | recommendation=`promote_efficiency_recovery_fix` |
| `python3 scripts/run_hidden_style_eval.py` | 48 cases, 0 failed cases |
| `python3 scripts/check_submission_ready.py` | ok=true, default strategy is `SQL_FIRST_API_VERIFY`, query output count 73, secret scan clean |
| `.venv/bin/python -m pytest -q` | 1173 passed, 1 skipped |
| `python3 scripts/generate_sdk_usage_audit.py` | runtime_llm_direct_http_hits=0 |
| `git diff --check` | passed |

Note: plain `python3 -m pytest -q` uses `/opt/homebrew/opt/python@3.14/bin/python3.14` in this shell and failed earlier because that interpreter lacks pytest. The full suite was therefore run with the repository venv interpreter.

## Benchmark Verdict
V2 is safe to keep as a research/shadow path and safe to continue benchmarking with timeouts, but not safe to promote. It remains far below `SQL_FIRST_API_VERIFY` on strict public/dev metrics and still has semantic-gate failures.
