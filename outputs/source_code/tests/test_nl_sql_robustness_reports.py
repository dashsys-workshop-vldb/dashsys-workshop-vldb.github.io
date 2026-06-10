from __future__ import annotations

import json

from scripts.run_multi_llm_backend_robustness import run_multi_llm_backend_robustness
from scripts.run_nl_sql_paraphrase_consistency import run_nl_sql_paraphrase_consistency
from scripts.run_nl_sql_robustness_audit import run_nl_sql_robustness_audit
from scripts.run_schema_aware_sql_feedback_loop import (
    ROBUSTNESS_SENTENCE,
    run_schema_aware_sql_feedback_loop,
)


def test_nl_sql_robustness_audit_writes_template_dependency_score(tiny_project):
    report = run_nl_sql_robustness_audit(tiny_project, include_generated=False, max_groups=1)

    report_path = tiny_project.outputs_dir / "reports" / "nl_sql_robustness_audit.json"
    assert report_path.exists()
    parsed = json.loads(report_path.read_text(encoding="utf-8"))
    assert parsed["diagnostic_only"] is True
    assert parsed["official_score_claim"] is False
    assert parsed["promotion_allowed"] is False
    assert "template_dependency_score" in parsed["metrics"]
    assert parsed["metrics"]["semantic_group_count"] == 1
    assert {row["variant_kind"] for row in parsed["rows"]} >= {"original", "synonym_substitution"}


def test_paraphrase_consistency_report_records_instability_dimensions(tiny_project):
    report = run_nl_sql_paraphrase_consistency(tiny_project, include_generated=False, max_groups=1)

    report_path = tiny_project.outputs_dir / "reports" / "nl_sql_paraphrase_consistency.json"
    assert report_path.exists()
    assert report["diagnostic_only"] is True
    assert report["promotion_allowed"] is False
    assert "route_changed" in report["instability_definitions"]
    group = report["groups"][0]
    assert "paraphrase_consistency_score" in group
    assert {"route_changed", "table_changed", "join_changed", "count_changed", "answer_intent_changed"} <= set(group["instabilities"])


def test_multi_llm_robustness_does_not_execute_hosted_llm_calls(tiny_project):
    report = run_multi_llm_backend_robustness(tiny_project)

    report_path = tiny_project.outputs_dir / "reports" / "multi_llm_backend_robustness.json"
    assert report_path.exists()
    assert report["diagnostic_only"] is True
    assert report["llm_calls_executed"] == 0
    assert any(item["backend"] == "deterministic_only" and item["executed"] for item in report["backends"])
    assert any(item["backend"] == "no_llm_fallback" and item["executed"] for item in report["backends"])


def test_schema_aware_feedback_loop_keeps_runtime_unpromoted(tiny_project):
    # Create the upstream robustness reports through their public helpers so the
    # feedback loop exercises the normal JSON-driven path used by the CLI.
    run_nl_sql_robustness_audit(tiny_project, include_generated=False, max_groups=1)
    run_nl_sql_paraphrase_consistency(tiny_project, include_generated=False, max_groups=1)
    report = run_schema_aware_sql_feedback_loop(tiny_project)

    feedback_path = tiny_project.outputs_dir / "reports" / "schema_aware_sql_feedback_loop.json"
    summary_path = tiny_project.outputs_dir / "reports" / "robustness_first_system_summary.json"
    assert feedback_path.exists()
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert report["promotion_allowed"] is False
    assert report["runtime_change_applied"] is False
    assert report["packaged_default_changed"] is False
    assert report["promotion_decision"]["decision"] == "keep_trial_only"
    assert summary["robustness_principle"] == ROBUSTNESS_SENTENCE
    assert summary["promotion_allowed"] is False
