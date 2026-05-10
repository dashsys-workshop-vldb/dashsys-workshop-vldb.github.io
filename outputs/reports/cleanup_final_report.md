# Redundant File Cleanup Report

- Dry run: True
- Applied: False
- Candidate rows: 6
- Actual deleted: 0
- Would delete: 6
- Previously deleted duplicates: 0
- Refused: 0
- No protected files deleted: True
- Files before cleanup: 18098
- Files after cleanup: 18098
- Reports consolidated: 0
- Final submission format unchanged: True
- check_submission_ready passed: True
- Secret scan passed: True
- Validation commands recorded: 19
- Required validation commands missing: 0

## Actions

- `.pytest_cache`: would_delete (dry_run)
- `outputs/cache`: would_delete (dry_run)
- `outputs/llm_controller_baseline_backend`: would_delete (dry_run)
- `outputs/llm_strict_eval`: would_delete (dry_run)
- `outputs/source_code`: would_delete (dry_run)
- `outputs/tmp`: would_delete (dry_run)

## Validation Commands

- `python3 -m pytest -q`: passed
- `python3 scripts/run_dev_eval.py --strict`: passed
- `python3 scripts/run_hidden_style_eval.py`: passed
- `python3 scripts/check_llm_sdk_backend.py`: passed
- `python3 scripts/run_llm_baseline_eval.py`: passed
- `python3 scripts/run_llm_strict_baseline_eval.py`: passed
- `python3 scripts/run_llm_hidden_style_diagnostic.py`: passed
- `python3 scripts/generate_winner_readiness_report.py`: passed
- `python3 scripts/generate_research_inspired_report.py`: passed
- `python3 scripts/generate_system_status_dashboard.py`: passed
- `python3 scripts/generate_technique_visual_cards.py`: passed
- `python3 scripts/generate_visualization_index.py`: passed
- `python3 scripts/package_submission.py`: passed
- `python3 scripts/package_query_outputs.py`: passed
- `python3 scripts/check_submission_ready.py`: passed
- `python3 scripts/generate_consolidated_reports.py`: passed
- `python3 scripts/audit_redundant_files.py`: passed
- `python3 scripts/cleanup_redundant_files.py --dry-run --write-report`: passed
- `rg -n secret scan`: passed

## Skipped Validation Commands

- None recorded.

## Missing Required Validation Commands

- None.

## Generated Reports

- `outputs/reports/report_index.md`: present
- `outputs/reports/report_index.json`: present
- `outputs/reports/system_summary.md`: present
- `outputs/reports/system_summary.json`: present
- `outputs/reports/llm_baseline_summary.md`: present
- `outputs/reports/llm_baseline_summary.json`: present
- `outputs/reports/accuracy_and_bottleneck_summary.md`: present
- `outputs/reports/accuracy_and_bottleneck_summary.json`: present
- `outputs/reports/visualization_summary.md`: present
- `outputs/reports/visualization_summary.json`: present
- `outputs/reports/cleanup_audit.md`: present
- `outputs/reports/cleanup_audit.json`: present
- `outputs/reports/cleanup_final_report.md`: present
- `outputs/reports/cleanup_final_report.json`: present
- `outputs/winner_readiness_report.md`: present
- `outputs/winner_readiness_report.json`: present
- `outputs/final_research_inspired_improvement_report.md`: present
- `outputs/final_research_inspired_improvement_report.json`: present
- `outputs/visualizations/index.md`: present
- `outputs/visualizations/index.json`: present
- `outputs/visualizations/system_status_dashboard.md`: present
- `outputs/visualizations/system_status_dashboard.json`: present
- `outputs/visualizations/technique_visual_cards.md`: present
- `outputs/visualizations/technique_visual_cards.json`: present

## Would Delete Files

- `.pytest_cache`
- `outputs/cache`
- `outputs/llm_controller_baseline_backend`
- `outputs/llm_strict_eval`
- `outputs/source_code`
- `outputs/tmp`

## Final Response Checklist

- files changed
- reports generated
- files deleted, if any
- validation commands run
- validation results
- skipped commands and reasons, if any
- check_submission_ready status
- secret scan status
- SQL_FIRST_API_VERIFY unchanged confirmation
- final submission format unchanged confirmation
