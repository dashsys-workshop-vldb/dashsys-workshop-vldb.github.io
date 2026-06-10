# Overnight Autonomous Improvement Report

- Iterations: `1`
- Best packaged strict score: `0.6553`
- Best isolated score: `0.6558`
- 0.70 reached: `False`
- 0.75 reached: `False`
- check_submission_ready: `True`
- Secret scan: `passed_no_hits`

## Promoted

- Batch-family dry-run endpoint-aware unavailable answer wording, backed by recorded API endpoint path/params only.

## Shadow Only / Rejected

- Broad endpoint-aware dry-run wording for non-batch families was trialed in /tmp and rejected because strict score regressed to 0.6447.
- LLM baseline remains keep_shadow_only.

## Validation

- `python3 -m pytest -q`: passed (322 passed)
- `python3 scripts/run_dev_eval.py --strict`: passed (SQL_FIRST_API_VERIFY strict=0.6553)
- `python3 scripts/run_hidden_style_eval.py`: passed (48/48)
- `python3 scripts/check_llm_sdk_backend.py`: completed_diagnostic (command exited 0; backend report ok=false in current environment)
- `python3 scripts/run_llm_baseline_eval.py`: passed (rows=105)
- `python3 scripts/run_llm_strict_baseline_eval.py`: passed (strict_scoring_status=available; recommendation=keep_shadow_only)
- `python3 scripts/run_llm_hidden_style_diagnostic.py`: passed (diagnostic_complete)
- `python3 scripts/generate_winner_readiness_report.py`: passed (fresh=true)
- `python3 scripts/generate_research_inspired_report.py`: passed (reports regenerated)
- `python3 scripts/generate_system_status_dashboard.py`: passed (reports regenerated)
- `python3 scripts/generate_technique_visual_cards.py`: passed (cards=47)
- `python3 scripts/generate_visualization_index.py`: passed (entries=44)
- `python3 scripts/generate_consolidated_reports.py`: passed (reports regenerated)
- `python3 scripts/audit_redundant_files.py`: passed (safe_to_delete=6)
- `python3 scripts/cleanup_redundant_files.py --dry-run --write-report`: passed (dry_run=true; deleted=0)
- `python3 scripts/package_submission.py`: passed (ok=true)
- `python3 scripts/package_query_outputs.py`: passed (manifest regenerated; duplicate protected files restored afterward)
- `python3 scripts/check_submission_ready.py`: passed (ok=True; query_output_count=107)
- `secret scan`: passed (no hits)

## Recommendation

Submit-ready improved packaged SQL_FIRST_API_VERIFY version; 0.70/0.75 not reached; continue answer-quality work in future targeted trials.
