from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.generate_project_mermaid_visualizations import generate_project_mermaid_visualizations


SECRET_RE = re.compile(
    ("Authorization" + r":\s*" + "Bearer")
    + r"|"
    + ("sk" + r"-[A-Za-z0-9_-]{12,}")
    + r"|"
    + ("ADOBE_ACCESS" + "_TOKEN=")
    + r"|"
    + ("OPENAI_API" + "_KEY=")
    + r"|"
    + ("ANTHROPIC_API" + "_KEY=")
    + r"|"
    + ("CLIENT" + "_SECRET=")
    + r"|"
    + ("x-api" + "-key:"),
    re.IGNORECASE,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_sources(outputs: Path) -> None:
    reports = outputs / "reports"
    visualizations = outputs / "visualizations"
    _write_json(
        reports / "report_index.json",
        {
            "report_type": "report_index",
            "canonical_reports": ["outputs/reports/system_summary.md"],
            "key_visualizations": ["outputs/visualizations/end_to_end_system_dataflow.html"],
            "live_adobe_api_readiness": {"full_run_blocker_path": "outputs/reports/live_api_full_run_blocker.md"},
        },
    )
    (reports / "report_index.md").write_text("# Consolidated Report Index\n", encoding="utf-8")
    _write_json(
        reports / "system_summary.json",
        {
            "report_type": "system_summary",
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "final_submission_ready": True,
            "hidden_style": {"label": "48/48"},
        },
    )
    (reports / "system_summary.md").write_text("# System Summary\n", encoding="utf-8")
    _write_json(
        reports / "workflow_decision_map.json",
        {"report_type": "workflow_decision_map", "stage_count": 7, "decisions": ["route", "plan", "answer"]},
    )
    _write_json(
        reports / "workflow_decision_audit.json",
        {"report_type": "workflow_decision_audit", "total_queries": 35, "overall_status": "complete"},
    )
    _write_json(
        reports / "live_api_full_run_blocker.json",
        {
            "guard_decision": "blocked",
            "live_success_count": 0,
            "failure_counts": {"auth_error": 3, "sandbox_scope_issue": 4},
            "safe_rerun_commands": ["python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get"],
        },
    )
    _write_json(
        reports / "adobe_access_waiting_status.json",
        {
            "report_type": "adobe_access_waiting_status",
            "live_success_count": 0,
            "usable_live_api_evidence_count": 0,
            "recommended_command": "python3 scripts/run_post_permission_live_api_verification.py",
        },
    )
    _write_json(
        reports / "context7_code_alignment_audit.json",
        {
            "report_type": "context7_code_alignment_audit",
            "status": "complete",
            "summary": {"potential_bug_count": 0, "needs_manual_review_count": 1},
        },
    )
    visualizations.mkdir(parents=True, exist_ok=True)


def test_project_mermaid_visualizations_are_generated_from_reports(tiny_project):
    _seed_sources(tiny_project.outputs_dir)

    result = generate_project_mermaid_visualizations(tiny_project)

    expected = [
        "project_architecture_c4",
        "end_to_end_pipeline_mermaid",
        "live_adobe_api_status_mermaid",
        "report_generation_map",
    ]
    for stem in expected:
        md_path = tiny_project.outputs_dir / "visualizations" / f"{stem}.md"
        mmd_path = tiny_project.outputs_dir / "visualizations" / f"{stem}.mmd"
        assert md_path.exists(), stem
        assert mmd_path.exists(), stem
        md_text = md_path.read_text(encoding="utf-8")
        mmd_text = mmd_path.read_text(encoding="utf-8")
        assert "```mermaid" in md_text
        assert mmd_text.strip()
        assert "SQL_FIRST_API_VERIFY" in md_text + mmd_text
        assert "live_success guard" in md_text + mmd_text
        assert not SECRET_RE.search(md_text + mmd_text)

    audit = json.loads((tiny_project.outputs_dir / "reports" / "visualization_sync_audit.json").read_text(encoding="utf-8"))
    assert audit["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert audit["final_submission_ready"] is True
    assert audit["live_success_count"] == 0
    assert audit["source_reports_used"]
    assert all("sha256" in source for source in audit["source_reports_used"])
    assert result["audit_path"] == str(tiny_project.outputs_dir / "reports" / "visualization_sync_audit.json")


def test_consolidated_reports_regenerate_mermaid_visualization_workflow(tiny_project):
    _seed_sources(tiny_project.outputs_dir)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    key_visualizations = index["key_visualizations"]
    assert "outputs/visualizations/project_architecture_c4.md" in key_visualizations
    assert "outputs/visualizations/live_adobe_api_status_mermaid.md" in key_visualizations
    assert "outputs/reports/visualization_sync_audit.md/json" in index["post_change_validation"]["report_regeneration_targets"]
    assert (tiny_project.outputs_dir / "reports" / "visualization_sync_audit.json").exists()
