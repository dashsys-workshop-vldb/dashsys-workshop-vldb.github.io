# Redundant File Cleanup Report

- Dry run: True
- Applied: False
- Candidate rows: 6
- Deleted: 0
- Deleted files total: 89
- Would delete: 6
- Refused: 0
- No protected files deleted: True
- Files before cleanup: 17788
- Files after cleanup: 17788
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

## Deleted Files

- `outputs/final_submission/query_009/filled_system_prompt 2.txt`
- `outputs/final_submission/query_009/metadata 2.json`
- `outputs/final_submission/query_009/trajectory 2.json`
- `outputs/final_submission/query_014/filled_system_prompt 2.txt`
- `outputs/final_submission/query_014/metadata 2.json`
- `outputs/final_submission/query_014/trajectory 2.json`
- `outputs/final_submission/query_015/filled_system_prompt 2.txt`
- `outputs/final_submission/query_015/metadata 2.json`
- `outputs/final_submission/query_015/trajectory 2.json`
- `outputs/final_submission/query_017/filled_system_prompt 2.txt`
- `outputs/final_submission/query_017/metadata 2.json`
- `outputs/final_submission/query_017/trajectory 2.json`
- `outputs/final_submission/query_018/filled_system_prompt 2.txt`
- `outputs/final_submission/query_018/metadata 2.json`
- `outputs/final_submission/query_018/trajectory 2.json`
- `outputs/final_submission/query_019/filled_system_prompt 2.txt`
- `outputs/final_submission/query_019/metadata 2.json`
- `outputs/final_submission/query_019/trajectory 2.json`
- `outputs/final_submission/query_020/filled_system_prompt 2.txt`
- `outputs/final_submission/query_020/metadata 2.json`
- `outputs/final_submission/query_020/trajectory 2.json`
- `outputs/final_submission/query_021/filled_system_prompt 2.txt`
- `outputs/final_submission/query_021/metadata 2.json`
- `outputs/final_submission/query_021/trajectory 2.json`
- `outputs/final_submission/query_023/filled_system_prompt 2.txt`
- `outputs/final_submission/query_023/metadata 2.json`
- `outputs/final_submission/query_023/trajectory 2.json`
- `outputs/final_submission/query_026/filled_system_prompt 2.txt`
- `outputs/final_submission/query_026/metadata 2.json`
- `outputs/final_submission/query_026/trajectory 2.json`
- `outputs/final_submission/query_028/filled_system_prompt 2.txt`
- `outputs/final_submission/query_028/metadata 2.json`
- `outputs/final_submission/query_028/trajectory 2.json`
- `outputs/final_submission/query_029/filled_system_prompt 2.txt`
- `outputs/final_submission/query_029/metadata 2.json`
- `outputs/final_submission/query_029/trajectory 2.json`
- `outputs/final_submission/query_031/filled_system_prompt 2.txt`
- `outputs/final_submission/query_031/metadata 2.json`
- `outputs/final_submission/query_031/trajectory 2.json`
- `outputs/final_submission/query_033/filled_system_prompt 2.txt`
- `outputs/final_submission/query_033/metadata 2.json`
- `outputs/final_submission/query_033/trajectory 2.json`
- `outputs/final_submission/query_036/filled_system_prompt 2.txt`
- `outputs/final_submission/query_036/metadata 2.json`
- `outputs/final_submission/query_036/trajectory 2.json`
- `outputs/final_submission/query_037/filled_system_prompt 2.txt`
- `outputs/final_submission/query_037/metadata 2.json`
- `outputs/final_submission/query_037/trajectory 2.json`
- `outputs/final_submission/query_040/filled_system_prompt 2.txt`
- `outputs/final_submission/query_040/metadata 2.json`
- `outputs/final_submission/query_040/trajectory 2.json`
- `outputs/final_submission/query_047/filled_system_prompt 2.txt`
- `outputs/final_submission/query_047/metadata 2.json`
- `outputs/final_submission/query_047/trajectory 2.json`
- `outputs/final_submission/query_048/filled_system_prompt 2.txt`
- `outputs/final_submission/query_048/metadata 2.json`
- `outputs/final_submission/query_048/trajectory 2.json`
- `outputs/final_submission/query_049/filled_system_prompt 2.txt`
- `outputs/final_submission/query_049/metadata 2.json`
- `outputs/final_submission/query_049/trajectory 2.json`
- `outputs/final_submission/query_050/filled_system_prompt 2.txt`
- `outputs/final_submission/query_050/metadata 2.json`
- `outputs/final_submission/query_050/trajectory 2.json`
- `outputs/final_submission/query_052/filled_system_prompt 2.txt`
- `outputs/final_submission/query_052/metadata 2.json`
- `outputs/final_submission/query_052/trajectory 2.json`
- `outputs/final_submission/query_054/filled_system_prompt 2.txt`
- `outputs/final_submission/query_054/metadata 2.json`
- `outputs/final_submission/query_054/trajectory 2.json`
- `outputs/final_submission/query_056/filled_system_prompt 2.txt`
- `outputs/final_submission/query_056/metadata 2.json`
- `outputs/final_submission/query_056/trajectory 2.json`
- `outputs/final_submission/query_065/filled_system_prompt 2.txt`
- `outputs/final_submission/query_065/metadata 2.json`
- `outputs/final_submission/query_065/trajectory 2.json`
- `outputs/final_submission/query_067/filled_system_prompt 2.txt`
- `outputs/final_submission/query_067/metadata 2.json`
- `outputs/final_submission/query_067/trajectory 2.json`
- `outputs/final_submission/query_068/filled_system_prompt 2.txt`
- `outputs/final_submission/query_068/metadata 2.json`
- `outputs/final_submission/query_068/trajectory 2.json`
- `outputs/final_submission/query_071/filled_system_prompt 2.txt`
- `outputs/final_submission/query_071/metadata 2.json`
- `outputs/final_submission/query_071/trajectory 2.json`
- `outputs/final_submission/query_072/filled_system_prompt 2.txt`
- `outputs/final_submission/query_072/metadata 2.json`
- `outputs/final_submission/query_072/trajectory 2.json`
- `outputs/final_submission/source_code 2.zip`
- `outputs/final_submission/system_prompt_template 2.txt`

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
