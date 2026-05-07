from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIS_DIR = ROOT / "outputs" / "visualizations"

GENERATOR_SCRIPTS = [
    "scripts/generate_technique_catalog.py",
    "scripts/generate_system_end_to_end_visualization.py",
    "scripts/generate_query_dataflow_visualizations.py",
    "scripts/generate_technique_impact_visualizations.py",
    "scripts/generate_current_system_state_visualization.py",
    "scripts/generate_visualization_index.py",
]

REQUIRED_FILES = [
    "index.md",
    "index.json",
    "technique_catalog.md",
    "technique_catalog.json",
    "system_end_to_end.md",
    "system_end_to_end.json",
    "query_example_000_dataflow.md",
    "query_example_000_dataflow.json",
    "query_example_003_dataflow.md",
    "query_example_003_dataflow.json",
    "query_example_011_dataflow.md",
    "query_example_011_dataflow.json",
    "query_example_021_dataflow.md",
    "query_example_021_dataflow.json",
    "query_example_031_dataflow.md",
    "query_example_031_dataflow.json",
    "query_example_033_dataflow.md",
    "query_example_033_dataflow.json",
    "technique_impact_matrix.md",
    "technique_impact_matrix.json",
    "score_improvement_timeline.md",
    "score_improvement_timeline.json",
    "current_system_state.md",
    "current_system_state.json",
    "technique_dataflow_views.md",
    "technique_dataflow_views.json",
]


def run_generators() -> None:
    for script in GENERATOR_SCRIPTS:
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def test_visualization_generators_create_required_files_and_links():
    run_generators()
    for filename in REQUIRED_FILES:
        path = VIS_DIR / filename
        assert path.exists(), filename
        assert "final_submission" not in path.parts

    index_md = (VIS_DIR / "index.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", index_md):
        if link.startswith("http"):
            continue
        target = (VIS_DIR / link).resolve()
        assert target.exists(), link
        assert VIS_DIR.resolve() in target.parents or target == VIS_DIR.resolve()


def test_visualizations_have_readable_mermaid_and_no_raw_json_nodes():
    run_generators()
    markdown_files = [
        VIS_DIR / "system_end_to_end.md",
        VIS_DIR / "current_system_state.md",
        VIS_DIR / "technique_dataflow_views.md",
        VIS_DIR / "query_example_031_dataflow.md",
    ]
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        assert "```mermaid" in text
        for block in re.findall(r"```mermaid\n(.*?)```", text, flags=re.S):
            assert len(block) < 5000
            assert '{"' not in block
            assert "truncated_items" not in block


def test_visualization_state_matches_source_reports_and_no_secret_patterns():
    run_generators()
    state = json.loads((VIS_DIR / "current_system_state.json").read_text(encoding="utf-8"))
    winner = json.loads((ROOT / "outputs" / "winner_readiness_report.json").read_text(encoding="utf-8"))
    packaged = winner["packaged"]
    assert state["packaged_strict_final_score"] == packaged["strict_final_score"]
    assert state["correctness"] == packaged["strict_correctness"]
    assert state["hidden_style"]["passed_cases"] == winner["hidden_style_eval"]["passed_cases"]
    assert state["official_token_reduction_status"]["state"] == "promoted_default"
    assert state["compact_context_status"]["state"] == "disabled"
    assert state["repair_status"]["state"] == "disabled"

    catalog = json.loads((VIS_DIR / "technique_catalog.json").read_text(encoding="utf-8"))
    states = {item["technique_name"]: item["default_state"] for item in catalog["techniques"]}
    assert states["official-token reduction"] == "promoted_default"
    assert states["endpoint-family tie-break v2"] == "shadow_only"
    assert states["live-mode readiness diagnostics"] == "diagnostic_only"

    secret_pattern = re.compile(
        "|".join(
            [
                re.escape("sk" + "-or-"),
                "OPENROUTER_API_KEY" + "=" + ".*" + re.escape("sk"),
                "OPENAI_API_KEY" + "=" + ".*" + re.escape("sk"),
                "Authorization:" + r"\s*" + "Bearer",
            ]
        ),
        re.I,
    )
    for path in VIS_DIR.glob("*.md"):
        assert not secret_pattern.search(path.read_text(encoding="utf-8")), path
    for path in VIS_DIR.glob("*.json"):
        assert not secret_pattern.search(path.read_text(encoding="utf-8")), path
