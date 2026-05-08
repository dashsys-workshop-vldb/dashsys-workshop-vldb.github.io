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
    "scripts/generate_sql_prompt_storyboard_primary.py",
    "scripts/generate_executive_dashboard.py",
    "scripts/generate_prompt_storyboard_visualization.py",
    "scripts/generate_prompt_transformation_visualization.py",
    "scripts/generate_end_to_end_execution_visualization.py",
    "scripts/generate_technique_pipeline_map.py",
    "scripts/generate_technique_visual_cards.py",
    "scripts/generate_system_status_dashboard.py",
    "scripts/generate_score_bottleneck_dashboard.py",
    "scripts/generate_visualization_index.py",
]

REQUIRED_FILES = [
    "index.md",
    "index.json",
    "executive_dashboard.md",
    "executive_dashboard.json",
    "sql_prompt_storyboard_primary.md",
    "sql_prompt_storyboard_primary.json",
    "prompt_storyboard_primary.md",
    "prompt_storyboard_primary.json",
    "prompt_transformation_primary.md",
    "prompt_transformation_primary.json",
    "end_to_end_execution_primary.md",
    "end_to_end_execution_primary.json",
    "technique_pipeline_map.md",
    "technique_pipeline_map.json",
    "technique_visual_cards.md",
    "technique_visual_cards.json",
    "system_status_dashboard.md",
    "system_status_dashboard.json",
    "score_bottleneck_dashboard.md",
    "score_bottleneck_dashboard.json",
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
        VIS_DIR / "executive_dashboard.md",
        VIS_DIR / "sql_prompt_storyboard_primary.md",
        VIS_DIR / "prompt_storyboard_primary.md",
        VIS_DIR / "prompt_transformation_primary.md",
        VIS_DIR / "end_to_end_execution_primary.md",
        VIS_DIR / "technique_pipeline_map.md",
        VIS_DIR / "system_end_to_end.md",
        VIS_DIR / "current_system_state.md",
        VIS_DIR / "technique_dataflow_views.md",
        VIS_DIR / "query_example_031_dataflow.md",
    ]
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        assert "```mermaid" in text
        for block in re.findall(r"```mermaid\n(.*?)```", text, flags=re.S):
            max_block_chars = 15000 if path.name == "sql_prompt_storyboard_primary.md" else 5000
            assert len(block) < max_block_chars
            assert '{"' not in block
            assert "truncated_items" not in block


def test_supervisor_pages_show_primary_prompt_bottleneck_and_reading_guides():
    run_generators()
    raw_prompt = "How many schemas do I have?"
    supervisor_pages = [
        "executive_dashboard.md",
        "prompt_storyboard_primary.md",
        "prompt_transformation_primary.md",
        "end_to_end_execution_primary.md",
        "technique_pipeline_map.md",
        "technique_visual_cards.md",
        "system_status_dashboard.md",
        "score_bottleneck_dashboard.md",
    ]
    for filename in supervisor_pages:
        text = (VIS_DIR / filename).read_text(encoding="utf-8")
        assert "## How To Read This Page" in text

    for filename in ["executive_dashboard.md", "sql_prompt_storyboard_primary.md", "prompt_transformation_primary.md", "end_to_end_execution_primary.md"]:
        text = (VIS_DIR / filename).read_text(encoding="utf-8")
        assert raw_prompt in text
        assert "example_031" not in text


def test_sql_primary_storyboard_is_sql_backed_and_visual_first():
    run_generators()
    data = json.loads((VIS_DIR / "sql_prompt_storyboard_primary.json").read_text(encoding="utf-8"))
    text = (VIS_DIR / "sql_prompt_storyboard_primary.md").read_text(encoding="utf-8")
    assert data["query_id"] == "example_011"
    assert data["raw_prompt"] == "How many schemas do I have?"
    assert data["selected_table"] == "dim_blueprint"
    assert data["selected_column"] == "BLUEPRINTID"
    assert data["aggregation"] == "COUNT DISTINCT"
    generated_sql = data["generated_sql"]
    assert generated_sql and generated_sql != "unavailable"
    assert generated_sql == 'SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B'
    assert "Prompt-to-SQL mapping" in text
    assert "&quot;schemas&quot; → dim_blueprint" in text
    assert "&quot;how many&quot; → COUNT DISTINCT" in text
    assert 'COUNT DISTINCT B.&quot;BLUEPRINTID&quot;' in text
    assert 'FROM &quot;dim_blueprint&quot;' in text
    assert "B.'BLUEPRINTID'" not in text
    assert "'dim_blueprint'" not in text
    assert "SELECT COUNT(DISTINCT" not in text
    assert "blueprint_count" in text
    assert "blueprint_count = 74" in text
    assert data["sql_result_summary"] == "blueprint_count = 74"
    assert data["final_answer"] in text
    assert data["api_branch_summary"] == "dry-run verification only; not answer source"
    assert "dry-run verification only" in text
    assert "not answer source" in text
    assert "SQL is the answer source" in text
    assert "SQL evidence = 74 schemas" in text
    assert "SQL_ONLY" in text
    assert "generic_sql_first" in text
    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", text, flags=re.S)
    assert len(mermaid_blocks) == 1
    assert mermaid_blocks[0].lstrip().startswith("flowchart")
    assert "sequenceDiagram" not in text
    assert "journey" not in text
    assert "stateDiagram" not in text
    assert "| --- |" not in text
    assert "```sql" not in text
    assert "confidence=" not in text
    assert "evidence=1 field(s)" not in text


def test_prompt_transformation_and_execution_visual_contracts():
    run_generators()
    transformation = json.loads((VIS_DIR / "prompt_transformation_primary.json").read_text(encoding="utf-8"))
    assert transformation["query_id"] == "example_011"
    assert "How many schemas do I have?" in (VIS_DIR / "prompt_transformation_primary.md").read_text(encoding="utf-8")
    panel_titles = {panel["title"] for panel in transformation["panels"]}
    assert "Raw → normalized" in panel_titles
    assert "Normalized → tokens/entities" in panel_titles
    assert "Tokens/entities → query analysis" in panel_titles
    assert "Analysis → context card" in panel_titles
    assert "Context → selected plan" in panel_titles
    assert "Plan → evidence" in panel_titles
    assert "Evidence → final answer" in panel_titles

    execution_md = (VIS_DIR / "end_to_end_execution_primary.md").read_text(encoding="utf-8")
    execution = json.loads((VIS_DIR / "end_to_end_execution_primary.json").read_text(encoding="utf-8"))
    assert execution["query_id"] == "example_011"
    assert "How many schemas do I have?" in execution_md
    assert "flowchart" in execution_md
    assert "sequenceDiagram" in execution_md


def test_visualization_index_first_links_match_sql_primary_order():
    run_generators()
    index_md = (VIS_DIR / "index.md").read_text(encoding="utf-8")
    links = re.findall(r"\[([^\]]+\.md)\]\(([^)]+)\)", index_md)
    first_links = [link for _, link in links[:7]]
    assert first_links == [
        "executive_dashboard.md",
        "sql_prompt_storyboard_primary.md",
        "prompt_transformation_primary.md",
        "end_to_end_execution_primary.md",
        "technique_pipeline_map.md",
        "system_status_dashboard.md",
        "score_bottleneck_dashboard.md",
    ]


def test_technique_visual_cards_cover_required_names_status_and_runtime_path():
    run_generators()
    cards = json.loads((VIS_DIR / "technique_visual_cards.json").read_text(encoding="utf-8"))["cards"]
    by_name = {card["technique_name"]: card for card in cards}
    required_names = {
        "query_normalizer",
        "query_tokens",
        "relevance_scorer",
        "query_analysis",
        "metadata_selector",
        "prompt_router",
        "simple_prompt_gate",
        "SQL_FIRST_API_VERIFY",
        "SQL templates",
        "API templates",
        "planner",
        "executor",
        "endpoint catalog",
        "endpoint family ranker",
        "answer-shape v2",
        "supportable answer rewriter",
        "SQL-only API-skip guard",
        "official-token reduction",
        "evidence_bus",
        "context cards",
        "fast paths",
        "call budget",
        "evidence policy",
        "local knowledge index",
        "cache",
        "plan optimizer",
        "compact context experiment",
        "shadow repair",
        "AST-guided SQL candidate canary",
        "endpoint-family tie-break v2",
        "live-mode readiness diagnostics",
        "answer verifier",
        "answer reranker",
        "hidden-style eval",
        "leakage / robustness checks",
        "secret scan",
        "package readiness checks",
        "OpenRouter LLM rewrite search",
        "supportable dry-run rewrite validation",
        "autonomous packaged trials",
    }
    missing = required_names - set(by_name)
    assert not missing
    valid_statuses = {"promoted_default", "shadow_only", "default_off", "diagnostic_only"}
    valid_runtime_paths = {"packaged", "isolated_trial", "shadow_report", "diagnostic_report"}
    for card in cards:
        assert card["status"] in valid_statuses
        assert card["runtime_path"] in valid_runtime_paths


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
