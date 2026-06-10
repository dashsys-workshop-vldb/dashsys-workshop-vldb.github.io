# Hardcoded Runtime And Score Path Audit

- Scanned files: `48320`
- Hits: `596246`
- Unsafe runtime hardcodes: `2`
- Unsafe fake score hits: `0`
- Legacy simulated diagnostic hits: `43`
- Needs-review runtime pattern risks: `61`
- Simulated trace promotion eligible: `false`

## Classification Counts
- `legacy_simulated_diagnostic`: `43`
- `needs_review_gold_pattern_runtime_risk`: `61`
- `safe_eval_only_after_execution`: `2499`
- `safe_report_only`: `592681`
- `safe_runtime_guard`: `97`
- `safe_runtime_identifier_io`: `67`
- `safe_test_fixture`: `796`
- `unsafe_runtime_hardcode`: `2`

## Unsafe Runtime Hardcode Hits
- `dashagent/concise_llm_answer_rewriter.py:144` term=`gold`
- `dashagent/executor.py:1252` term=`gold`
