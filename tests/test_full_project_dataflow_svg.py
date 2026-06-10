from __future__ import annotations

import json
import re
from pathlib import Path

import scripts.generate_visualization_index as visualization_index
from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.generate_full_project_dataflow_svg import generate_full_project_dataflow_svg


SECRET_RE = re.compile(
    ("Authorization" + r"[:\s]")
    + r"|"
    + ("Bearer" + r"\s+[A-Za-z0-9._~+/=-]+")
    + r"|"
    + ("sk" + r"-[A-Za-z0-9_-]{12,}")
    + r"|"
    + ("ADOBE_ACCESS" + "_TOKEN")
    + r"|"
    + ("OPENAI_API" + "_KEY")
    + r"|"
    + ("ANTHROPIC_API" + "_KEY")
    + r"|"
    + ("CLIENT" + "_SECRET")
    + r"|"
    + r"\b[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_md(path: Path, text: str = "# report\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_sources(outputs: Path) -> None:
    reports = outputs / "reports"
    visualizations = outputs / "visualizations"
    _write_json(
        reports / "report_index.json",
        {"report_type": "report_index", "key_visualizations": [], "canonical_reports": []},
    )
    _write_md(reports / "report_index.md")
    _write_json(
        reports / "system_summary.json",
        {
            "report_type": "system_summary",
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "hidden_style": {"label": "48/48"},
            "final_submission_ready": True,
        },
    )
    _write_md(reports / "system_summary.md")
    _write_json(
        reports / "workflow_decision_map.json",
        {"report_type": "workflow_decision_map", "stage_count": 7, "status": "complete"},
    )
    _write_md(reports / "workflow_decision_map.md")
    _write_json(
        reports / "workflow_decision_audit.json",
        {"report_type": "workflow_decision_audit", "total_queries": 35, "status": "complete"},
    )
    _write_md(reports / "workflow_decision_audit.md")
    _write_json(
        reports / "live_api_full_run_blocker.json",
        {
            "report_type": "live_api_full_run_blocker",
            "guard_decision": "blocked",
            "live_success_count": 0,
            "failure_counts": {"auth_error": 3, "sandbox_scope_issue": 4},
        },
    )
    _write_md(reports / "live_api_full_run_blocker.md")
    _write_json(
        reports / "adobe_access_waiting_status.json",
        {
            "report_type": "adobe_access_waiting_status",
            "current_guard_status": "blocked",
            "what_is_blocked": ["full live eval", "live generated prompt suite"],
        },
    )
    _write_md(reports / "adobe_access_waiting_status.md")
    _write_json(
        reports / "context7_code_alignment_audit.json",
        {"report_type": "context7_code_alignment_audit", "status": "complete"},
    )
    _write_md(reports / "context7_code_alignment_audit.md")
    _write_json(
        reports / "generated_prompt_suite_local_diagnostic.json",
        {
            "report_type": "generated_prompt_suite_local_diagnostic",
            "diagnostic_only": True,
            "runtime_pass_count": 250,
        },
    )
    _write_md(reports / "generated_prompt_suite_local_diagnostic.md")
    _write_json(
        reports / "local_gap_manual_review.json",
        {"report_type": "local_gap_manual_review", "advisory_only": True},
    )
    _write_md(reports / "local_gap_manual_review.md")
    _write_json(
        reports / "superpowers_fix_decision.json",
        {"report_type": "superpowers_fix_decision", "runtime_change_applied": False},
    )
    _write_md(reports / "superpowers_fix_decision.md")
    for stem in [
        "end_to_end_pipeline_mermaid",
        "project_architecture_c4",
        "live_adobe_api_status_mermaid",
        "report_generation_map",
    ]:
        _write_md(visualizations / f"{stem}.md", f"# {stem}\nSQL_FIRST_API_VERIFY\n")


def test_full_project_svg_generator_creates_single_audited_svg(tiny_project):
    _seed_sources(tiny_project.outputs_dir)

    result = generate_full_project_dataflow_svg(tiny_project)

    vis = tiny_project.outputs_dir / "visualizations"
    reports = tiny_project.outputs_dir / "reports"
    svg = vis / "full_project_dataflow.svg"
    md = vis / "full_project_dataflow.md"
    meta = vis / "full_project_dataflow.json"
    audit_json = reports / "full_project_dataflow_svg_audit.json"
    audit_md = reports / "full_project_dataflow_svg_audit.md"
    for path in [svg, md, meta, audit_json, audit_md]:
        assert path.exists(), path

    svg_text = svg.read_text(encoding="utf-8")
    assert svg_text.count("<svg") == 1
    for label in [
        "SQL_FIRST_API_VERIFY",
        "EvidenceBus",
        "live_success guard",
        "generated prompts diagnostic-only",
        "final_submission_ready",
        "SDK-only LLM",
        "Context7 audit",
        "Post-permission verification",
    ]:
        assert label in svg_text
    assert not SECRET_RE.search(svg_text)

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert payload["live_success_count"] == 0
    assert payload["final_submission_ready"] is True
    assert payload["runtime_behavior_changed"] is False
    assert payload["credentials_accessed"] is False
    assert payload["env_local_accessed"] is False
    assert payload["node_count"] > 50
    assert payload["edge_count"] > 45
    assert "Packaging / Submission Layer" in payload["sections"]

    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["checks"]["svg_exists"] is True
    assert audit["checks"]["contains_sql_first_api_verify"] is True
    assert audit["checks"]["contains_no_credential_patterns"] is True
    assert audit["runtime_behavior_changed"] is False
    assert result["svg_path"] == str(svg)


def test_full_project_svg_is_linked_from_consolidated_indexes(tiny_project):
    _seed_sources(tiny_project.outputs_dir)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    visualization = json.loads((tiny_project.outputs_dir / "reports" / "visualization_summary.json").read_text(encoding="utf-8"))
    assert "outputs/visualizations/full_project_dataflow.svg" in index["key_visualizations"]
    assert "outputs/visualizations/full_project_dataflow.md" in index["key_visualizations"]
    assert "outputs/reports/full_project_dataflow_svg_audit.md/json" in index["post_change_validation"]["report_regeneration_targets"]
    assert visualization["single_svg_project_overview"] == "outputs/visualizations/full_project_dataflow.svg"


def test_visualization_index_links_full_project_svg(tiny_project, monkeypatch):
    vis = tiny_project.outputs_dir / "visualizations"
    vis.mkdir(parents=True, exist_ok=True)
    (vis / "full_project_dataflow.svg").write_text("<svg></svg>", encoding="utf-8")
    monkeypatch.setattr(visualization_index, "VIS_DIR", vis)
    monkeypatch.setattr(visualization_index, "required_visualization_files", lambda: ["full_project_dataflow.svg"])

    entries = visualization_index.build_entries()

    assert entries == [
        {
            "file": "full_project_dataflow.svg",
            "path": str(vis / "full_project_dataflow.svg"),
            "exists": True,
            "kind": "svg",
            "link": "full_project_dataflow.svg",
        }
    ]
