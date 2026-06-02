# Final Two Rows Benchmark Summary

## Scope

This report records the benchmark and gate commands run after the focused V2 SDK-toolcall Semantic IR smoke passed. It does not promote V2 and does not change the packaged default.

## Focused Smoke Prerequisite

The fresh Hermes V2 toolcall smoke completed successfully:

- `passed_count`: 7/7
- `timeout_count`: 0
- `unsupported_claims`: 0
- `no_tool_fp`: 0
- `final_semantic_gate_final_failures`: 0
- `runtime_fact_count`: 9

## Strict Dev Eval Attempts

| Strategy | Command | Result |
|---|---|---|
| `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` | `python3 scripts/run_dev_eval.py --strict --strategies ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` | Attempted. The run wrote 35 V2 trajectory files under `outputs/eval/example_000..034/robust_generalized_harness_candidate_v2/`, then hung during local LLM execution and was manually terminated. No reliable V2 strict score was produced. |
| `SQL_FIRST_API_VERIFY` | `python3 scripts/run_dev_eval.py --strict --strategies SQL_FIRST_API_VERIFY` | Completed. |

## SQL_FIRST_API_VERIFY Strict Baseline

| Metric | Value |
|---|---:|
| examples | 35 |
| final | 0.6562 |
| correctness | 0.6812 |
| answer | 0.3223 |
| SQL | 0.9333 over 15 scored rows |
| API | 0.9791 over 31 scored rows |
| tool calls | 1.4571 |
| runtime seconds | 0.0250 |
| estimated tokens | 796.8571 |

Because the V2 strict run did not complete, there is no valid V2-vs-SQL_FIRST strict delta.

## Gates

| Command | Result |
|---|---|
| `python3 scripts/run_semantic_route_promotion_gate.py` | `promotion_allowed=false`, recommendation `keep_shadow_only`; packaged runtime unchanged; hidden-style gate passed; no concrete-data plain LLM direct gate passed. |
| `python3 scripts/run_integrated_robustness_gate.py` | Passed with recommendation `promote_efficiency_recovery_fix`; this is not a V2 promotion decision. |
| `python3 scripts/run_hidden_style_eval.py` | 48/48 cases passed. |
| `python3 scripts/check_submission_ready.py` | `ok=true`; default strategy remains `SQL_FIRST_API_VERIFY`; query output count `73`; secret scan `ok=true`. |

## Validation

| Command | Result |
|---|---|
| `python3 -m pytest -q` | `1138 passed, 1 skipped` |
| `python3 scripts/generate_sdk_usage_audit.py` | `runtime_llm_direct_http_hits=0` |
| `git diff --check` | passed |

## Decision

- Safe to keep: yes.
- Safe to commit: yes.
- Safe to benchmark: focused smoke passed; full V2 strict benchmark needs a timeout/hang fix before reliable scoring.
- Safe to promote V2: no.

## Remaining Blocker

The focused smoke is now clean, but `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` strict dev eval still hangs under the local Qwen3.6 configuration. Treat V2 as shadow-only until that benchmark hang is diagnosed and a completed strict result is available.
