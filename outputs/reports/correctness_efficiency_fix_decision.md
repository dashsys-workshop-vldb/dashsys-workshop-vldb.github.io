# Correctness + Efficiency Fix Decision

- Decision: `speed_only_patch_needs_validation`
- Best candidate: `compact_tool_schema`
- Runtime change applied: `False`
- Official overall score claim: `False`
- Organizer weights known: `False`

At least one speed-only candidate Pareto-dominates the baseline, but evidence is shadow-simulated and still needs strict/hidden/submission validation before implementation.

## Required Before Promotion

- `correctness_no_regression_required`: `True`
- `hidden_style_48_48_required`: `True`
- `check_submission_ready_required`: `True`
- `direct_http_hits_must_remain_zero`: `True`
- `final_submission_format_unchanged_required`: `True`
- `unsupported_claim_increase_allowed`: `False`
- `high_scoring_official_row_regression_allowed`: `False`
- `generated_prompt_broad_breakage_allowed`: `False`
- `hardcoding_allowed`: `False`
- `patch_must_be_small_and_general`: `True`

## Follow-Up Validation

- Implement at most one selected speed-only patch in the shadow/controller path.
- Run python3 scripts/run_dev_eval.py --strict and verify correctness does not regress.
- Run python3 scripts/run_hidden_style_eval.py and verify 48/48.
- Run python3 scripts/run_generated_prompt_suite_local_diagnostic.py and inspect broad breakage.
- Run python3 scripts/check_submission_ready.py.
- Run python3 scripts/generate_sdk_usage_audit.py and verify runtime_llm_direct_http_hits=0.
- Run python3 -m pytest -q.
