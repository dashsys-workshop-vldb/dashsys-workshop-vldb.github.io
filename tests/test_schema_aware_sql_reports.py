from __future__ import annotations

import json

from scripts.run_schema_aware_sql_trial import run_schema_aware_sql_trial
from scripts.run_sql_template_coverage_audit import run_sql_template_coverage_audit


def test_sql_template_coverage_audit_writes_report(tiny_project):
    report = run_sql_template_coverage_audit(tiny_project)

    report_path = tiny_project.outputs_dir / "reports" / "sql_template_coverage_audit.json"
    assert report_path.exists()
    parsed = json.loads(report_path.read_text(encoding="utf-8"))
    assert parsed["report_type"] == "sql_template_coverage_audit"
    assert parsed["diagnostic_only"] is True
    assert parsed["row_count"] >= 1
    assert {"template_gap", "table_selection_gap", "join_reasoning_gap", "count_distinct_gap", "where_condition_gap", "column_selection_gap", "no_sql_gap", "none"} <= set(parsed["required_likely_failure_enum"])
    assert report["promotion_allowed"] is False


def test_schema_aware_sql_trial_is_diagnostic_and_keeps_packaged_default(tiny_project):
    report = run_schema_aware_sql_trial(tiny_project)

    report_path = tiny_project.outputs_dir / "reports" / "schema_aware_sql_trial.json"
    assert report_path.exists()
    assert report["diagnostic_only"] is True
    assert report["promotion_allowed"] is False
    assert report["runtime_change_applied"] is False
    assert report["packaged_default_changed"] is False
    assert report["decision"]["decision"] == "keep_trial_only"
    assert (tiny_project.outputs_dir / "schema_aware_sql_trial" / "baseline" / "eval_results_strict.json").exists()
    assert (tiny_project.outputs_dir / "schema_aware_sql_trial" / "schema_aware" / "eval_results_strict.json").exists()
