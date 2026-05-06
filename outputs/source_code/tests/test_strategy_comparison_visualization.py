from __future__ import annotations

from pathlib import Path

from scripts.generate_all_dataflow_visualizations import write_index
from scripts.generate_strategy_comparison_visualization import build_strategy_markdown, write_strategy_comparison


def test_strategy_comparison_labels_raw_and_guided(tmp_path):
    summaries = [
        {
            "strategy": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
            "variant": "Raw",
            "route": {"mode": "n/a"},
            "context": {"context_mode": "n/a"},
            "sql": {"preview": "SELECT * FROM journey"},
            "api": {"endpoint": "n/a - no API call in trajectory"},
            "execution": {"tool_call_count": 1, "invalid_tool_calls": 1, "endpoint_repairs": 0},
            "evidence": {"evidence_available": False, "dry_run_only": False},
            "metrics": {"runtime": 1.0, "prompt_context_tokens": 100},
            "answer": {"final_answer_preview": "The executed query did not find evidence."},
        },
        {
            "strategy": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
            "variant": "Guided",
            "route": {"mode": "n/a"},
            "context": {"context_mode": "guided schema affordance"},
            "sql": {"preview": "SELECT * FROM dim_campaign"},
            "api": {"endpoint": "GET /ajo/journey"},
            "execution": {"tool_call_count": 2, "invalid_tool_calls": 0, "endpoint_repairs": 1},
            "evidence": {"evidence_available": True, "dry_run_only": True},
            "metrics": {"runtime": 1.4, "prompt_context_tokens": 180},
            "answer": {"final_answer_preview": "Guided answer."},
        },
    ]
    out_dir = tmp_path / "outputs" / "visualizations" / "example_000"
    files = write_strategy_comparison("example_000", summaries, out_dir)
    md = Path(files["md"]).read_text(encoding="utf-8")
    assert "Raw" in md
    assert "Guided" in md
    assert "GET /ajo/journey" in md
    assert "endpoint" in md.lower()


def test_visualization_index_links_generated_files(tmp_path):
    outputs_dir = tmp_path / "outputs"
    entries = [
        {
            "query_id": "example_000",
            "query": "When was the journey published?",
            "strategy": "SQL_FIRST_API_VERIFY",
            "variant": "n/a",
            "valid_trajectory": True,
            "dry_run_api": True,
            "endpoint_repaired": False,
            "zero_row_uncertain": False,
            "invalid_tool_calls": 0,
            "successful_evidence": 1,
            "dataflow_md": str(outputs_dir / "visualizations" / "example_000" / "sql_first_api_verify" / "dataflow.md"),
            "dataflow_html": str(outputs_dir / "visualizations" / "example_000" / "sql_first_api_verify" / "dataflow.html"),
        }
    ]
    files = write_index(outputs_dir, entries)
    md = Path(files["md"]).read_text(encoding="utf-8")
    assert "dataflow.md" in md
    assert "dry-run API" in md
    assert "successful evidence" in md


def test_strategy_markdown_missing_summaries_are_na():
    md = build_strategy_markdown("missing_query", [], "flowchart LR\n")
    assert "n/a" in md
